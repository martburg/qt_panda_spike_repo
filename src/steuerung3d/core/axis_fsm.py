from __future__ import annotations
from dataclasses import dataclass

from transitions import Machine

from .axis_types import AxisTelemetry, AxisRequest, AxisCommand
from .control_in import compute_control_in


# States: keep them controller-side and semantic
ST_DISCONNECTED = "disconnected"
ST_IDLE         = "idle"         # linked, but not claiming / not enabled
ST_CLAIMING     = "claiming"     # Intent=True, waiting for PLC to "ack" ownership (we can define ack later)
ST_READY        = "ready"        # claimed, not enabled
ST_ENABLING     = "enabling"     # requested enable, waiting enabled bit
ST_ACTIVE       = "active"       # enabled; motion allowed (subject to request)
ST_ESTOP        = "estop"        # safety not ok -> force safe outputs
ST_RECOVER      = "recover"      # after estop cleared: resync + re-claim + re-enable
ST_FAULT        = "fault"        # fault seen -> safe outputs until cleared


@dataclass
class AxisFsmConfig:
    controller_pid: str
    default_control_pid_tx: int = 0
    safe_modus: str = "E"         # in your legacy, 'E' seems “normal”
    idle_modus: str = "E"
    write_modus: str = "w"


class AxisFSM:
    """
    Controller-side state machine.

    Inputs per tick:
      - telemetry (decoded)
      - request (operator/controller intent)

    Output per tick:
      - AxisCommand (semantic), which adapter encodes into legacy downlink tokens.
    """
    def __init__(self, cfg: AxisFsmConfig):
        self.cfg = cfg
        self.machine = Machine(
            model=self,
            states=[ST_DISCONNECTED, ST_IDLE, ST_CLAIMING, ST_READY, ST_ENABLING, ST_ACTIVE, ST_ESTOP, ST_RECOVER, ST_FAULT],
            initial=ST_DISCONNECTED,
            auto_transitions=False,
        )

        # --- link transitions ---
        self.machine.add_transition("on_link_up",   ST_DISCONNECTED, ST_IDLE)
        self.machine.add_transition("on_link_down", "*",            ST_DISCONNECTED)

        # --- safety / fault hard overrides ---
        self.machine.add_transition("on_estop",     "*",            ST_ESTOP)
        self.machine.add_transition("on_fault",     "*",            ST_FAULT)

        # --- estop recovery path ---
        self.machine.add_transition("on_estop_cleared", ST_ESTOP,   ST_RECOVER)
        self.machine.add_transition("on_recovered",     ST_RECOVER, ST_CLAIMING)

        # --- claiming / ready / enable ---
        self.machine.add_transition("start_claim",  ST_IDLE,        ST_CLAIMING)
        self.machine.add_transition("claim_ok",     ST_CLAIMING,    ST_READY)
        self.machine.add_transition("enable_req",   ST_READY,       ST_ENABLING)
        self.machine.add_transition("enabled_ok",   ST_ENABLING,    ST_ACTIVE)
        self.machine.add_transition("disable_req",  ST_ACTIVE,      ST_READY)

        # --- fault recovery (placeholder) ---
        self.machine.add_transition("fault_cleared", ST_FAULT,      ST_IDLE)

    # ---------- public tick ----------
    def step(self, tel: AxisTelemetry, req: AxisRequest) -> AxisCommand:
        # 1) link gating
        if not tel.link_ok:
            if self.state != ST_DISCONNECTED:
                self.on_link_down()
            return self._cmd_safe(req, intent=False, resync=False)

        if self.state == ST_DISCONNECTED:
            self.on_link_up()

        # 2) hard safety/fault overrides
        if tel.estop_active:
            if self.state != ST_ESTOP:
                self.on_estop()
            # while estop: force safe, allow estop reset + resync request only
            return self._cmd_estop(req)

        if tel.fault_active:
            if self.state != ST_FAULT:
                self.on_fault()
            return self._cmd_safe(req, intent=False, resync=False)

        # if we *were* in estop and now cleared: go recover
        if self.state == ST_ESTOP and not tel.estop_active:
            self.on_estop_cleared()

        # 3) state behaviors
        if self.state == ST_IDLE:
            if req.want_claim:
                self.start_claim()
            return self._cmd_idle(req, intent=req.want_claim)

        if self.state == ST_CLAIMING:
            # define "claim ack": for now we treat it as "PLC echoes our PID in uplink field 0"
            # (in your ST uplink, field 0 is OwnPID; PLC sets OwnPID to '0000' on timeout)
            if tel.own_pid_rx == self.cfg.controller_pid:
                self.claim_ok()
            return self._cmd_idle(req, intent=True)

        if self.state == ST_READY:
            if req.want_enable:
                self.enable_req()
            return self._cmd_ready(req, intent=True)

        if self.state == ST_ENABLING:
            if tel.enabled:
                self.enabled_ok()
            # keep enable request asserted until we see enabled
            return self._cmd_enable(req, intent=True)

        if self.state == ST_ACTIVE:
            if not req.want_enable:
                self.disable_req()
                return self._cmd_ready(req, intent=True)
            return self._cmd_active(req, intent=True)

        if self.state == ST_RECOVER:
            # concrete recover sequence:
            #  - assert resync=1 for some ticks (req.want_resync may be set by controller policy)
            #  - once controller decides it's done, trigger on_recovered() and re-claim
            if req.want_resync:
                return self._cmd_recover(req)
            # if higher layer stops requesting resync, we proceed to reclaim
            self.on_recovered()
            return self._cmd_idle(req, intent=True)

        if self.state == ST_FAULT:
            # if fault cleared in telemetry we moved already; otherwise stay safe
            return self._cmd_safe(req, intent=False, resync=False)

        # fallback
        return self._cmd_safe(req, intent=False, resync=False)

    # ---------- command builders ----------
    def _base(
        self,
        req: AxisRequest,
        *,
        modus: str,
        intent: bool,
        resync: bool,
        enable: bool = False,
        motion: bool = False,
    ) -> AxisCommand:
        return AxisCommand(
            modus=modus,
            own_pid_tx=self.cfg.controller_pid,
            control_pid_tx=self.cfg.default_control_pid_tx,
            intent_str="True" if intent else "False",
            control_in=compute_control_in(enable=bool(enable), motion=bool(motion)),
            guide_control_ui=0,
            speed_soll=req.cmd_speed,
            guide_speed_soll=0.0,
            pos_soll=req.cmd_pos,
            estop_reset=1 if req.want_reset_estop else 0,
            resync=1.0 if resync else 0.0,
            gui_nothalt_in=1 if req.want_reset_estop else 0,
            write_params=req.write_params,
            params=None,
        )

    def _cmd_safe(self, req: AxisRequest, *, intent: bool, resync: bool) -> AxisCommand:
        # Safe: no motion, no enable implied, keep setpoints at 0
        safe_req = AxisRequest(
            want_enable=False,
            want_motion=False,
            want_claim=req.want_claim,
            want_resync=req.want_resync,
            want_reset_estop=req.want_reset_estop,
            cmd_speed=0.0,
            cmd_pos=0.0,
            write_params=False,
        )
        return self._base(safe_req, modus=self.cfg.safe_modus, intent=intent, resync=resync, enable=False, motion=False)

    def _cmd_estop(self, req: AxisRequest) -> AxisCommand:
        # During estop, don't try to own/enable; only pass reset/resync signals.
        return self._cmd_safe(req, intent=False, resync=req.want_resync)

    def _cmd_idle(self, req: AxisRequest, intent: bool) -> AxisCommand:
        return self._cmd_safe(req, intent=intent, resync=False)

    def _cmd_ready(self, req: AxisRequest, intent: bool) -> AxisCommand:
        # Ready = claimed but not enabled
        return self._cmd_safe(req, intent=intent, resync=False)

    def _cmd_enable(self, req: AxisRequest, intent: bool) -> AxisCommand:
        # Enabling = same setpoints, but you may set enable bit in control_in once mapped
        return self._base(req, modus=self.cfg.idle_modus, intent=intent, resync=False, enable=True, motion=False)

    def _cmd_active(self, req: AxisRequest, intent: bool) -> AxisCommand:
        # Active = allow motion setpoints through (already ramped/clamped elsewhere)
        return self._base(
            req,
            modus=self.cfg.idle_modus,
            intent=intent,
            resync=False,
            enable=True,
            motion=bool(req.want_motion),
        )

    def _cmd_recover(self, req: AxisRequest) -> AxisCommand:
        # Recover = claim + resync asserted (legacy uses ReSync==1 to clear EStoped)
        return self._base(req, modus=self.cfg.idle_modus, intent=True, resync=True, enable=False, motion=False)
