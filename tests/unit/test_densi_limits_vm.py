import sys

sys.path.insert(0, 'src')

from steuerung3d.apps.yellow.panels.densi.densi_limits_vm import compute_densi_limits_vm


def test_limits_vm_format_and_decimal_comma():
    vm = compute_densi_limits_vm(
        values={'HardMax': 1.234, 'HardMin': -0.1},
        limit_widgets={'HardMax': 'txtLimitHardMax', 'HardMin': 'txtLimitHardMin'},
    )
    assert vm.texts['txtLimitHardMax'] == '1,23 m'
    assert vm.texts['txtLimitHardMin'] == '-0,10 m'


def test_limits_vm_ignores_missing_keys():
    vm = compute_densi_limits_vm(values={'HardMax': 2.0}, limit_widgets={'UserMax': 'txtLimitUserMax'})
    assert vm.texts == {}
