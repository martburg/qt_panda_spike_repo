import sys

sys.path.insert(0, 'src')

from steuerung3d.apps.yellow.panels.densi.densi_lifetick_vm import compute_densi_lifetick_vm
from steuerung3d.core.state import AxisState, MachineState


def test_lifetick_vm_basic_diff():
    st = MachineState(axes={'Anton': AxisState(meta={'lifetick_tx': 10, 'lifetick_rx': 7})})
    vm = compute_densi_lifetick_vm(state=st, axis_id='Anton')
    assert vm.text == '3'


def test_lifetick_vm_wrap_16bit():
    st = MachineState(axes={'Anton': AxisState(meta={'lifetick_tx': 1, 'lifetick_rx': 0xFFFF})})
    vm = compute_densi_lifetick_vm(state=st, axis_id='Anton')
    assert vm.text == '2'


def test_lifetick_vm_missing_axis():
    st = MachineState()
    vm = compute_densi_lifetick_vm(state=st, axis_id='Anton')
    assert vm.text == '--'
