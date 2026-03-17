from hlf.vm.bytecode import BytecodeModule, Function, OpCode, load_bytecode


def test_bytecode_roundtrip_preserves_multi_operand_and_wide_instructions() -> None:
    module = BytecodeModule("roundtrip")
    function = Function("main", 0)
    function.code = [
        (OpCode.CALL, 7, 2),
        (OpCode.GAS_CHECK, 70000),
        OpCode.RETURN,
    ]
    module.add_function(function)
    module.entry_point = 0

    restored = load_bytecode(module.serialize())

    assert restored.functions[0].code == function.code