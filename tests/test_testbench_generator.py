import os

from fault_injection.simulation.testbench_generator import TestbenchGenerator


def test_generate_replaces_netlist_and_absolutizes_other_includes(tmpdir):
    source_dir = tmpdir.mkdir('src_tb')
    testbench_path = str(source_dir.join('tb.circuit'))

    with open(testbench_path, 'w') as handle:
        handle.write(
            'X1 a b 0 TOP\n'
            '.INCLUDE netlist.sub\n'
            '.INCLUDE subcircuit_files/PRIMITIVE.sub\n'
            '*.INCLUDE process_models/fastN_fastP.process\n'
            '.INCLUDE process_models/typical.process\n'
            '.TRAN 1m 2m 0\n'
            '.END\n'
        )

    out_dir = tmpdir.mkdir('corner_dir')
    output_path = str(out_dir.join('tb_out.circuit'))
    process_abs = str(tmpdir.join('typical.process'))

    TestbenchGenerator().generate(
        testbench_path, output_path, 'netlist_faulted.sub', process_abs,
        original_netlist_filename='netlist.sub'
    )

    with open(output_path, 'r') as handle:
        text = handle.read()

    lines = text.splitlines()

    assert '.INCLUDE netlist_faulted.sub' in lines
    assert any(
        line.startswith('.INCLUDE') and 'PRIMITIVE.sub' in line and
        os.path.isabs(line.split(None, 1)[1])
        for line in lines
    )
    assert '.INCLUDE {}'.format(process_abs) in lines
    # Le fichier process d'origine (relatif) est bien commente / neutralise.
    assert '*.INCLUDE process_models/typical.process' in lines
