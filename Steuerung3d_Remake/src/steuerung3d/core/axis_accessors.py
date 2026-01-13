from steuerung3d.core.axis_types import AxisTelemetry

def legacy_tel_or_default(ax: "AxisState", axis_id: str) -> AxisTelemetry:
    if isinstance(ax.tel, AxisTelemetry):
        return ax.tel
    # safe default when we haven't received uplink yet
    return AxisTelemetry(
        link_ok=False,
        name=axis_id,
        own_pid_rx="",
        lifetick_tx=0,
        status_word=0,
        guide_status_word=0,
        estop_status_dword=0,
        system_time="",
        pos_ist=ax.pos,
        vel_ist=ax.vel,
        estop_active=False,
        fault_active=ax.fault,
        enabled=ax.enabled,
    )
