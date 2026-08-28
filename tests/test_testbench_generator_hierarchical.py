import os

from fault_injection.simulation.testbench_generator import TestbenchGenerator


def test_hierarchical_testbench_replaces_only_the_target_netlist(tmpdir):
    """Reproduit le bug FILTER: un testbench qui inclut PRIMITIVE.sub,
    une dependance OPAMP1.sub, ET le netlist principal FILTER.sub. Seul
    FILTER.sub doit etre remplace par la version fautee; OPAMP1.sub doit
    rester une dependance intacte (chemin absolutise mais fichier reel)."""
    source_dir = tmpdir.mkdir('src_tb')
    testbench_path = str(source_dir.join('filter.circuit'))

    with open(testbench_path, 'w') as handle:
        handle.write(
            'X1 a b 0 FILTER\n'
            '.INCLUDE subcircuit_files/PRIMITIVE.sub\n'
            '.INCLUDE subcircuit_files/OPAMP1.sub\n'
            '.INCLUDE subcircuit_files/FILTER.sub\n'
            '.TRAN 1u 10u\n'
            '.END\n'
        )

    out_dir = tmpdir.mkdir('corner_dir')
    output_path = str(out_dir.join('tb_out.circuit'))
    process_abs = str(tmpdir.join('typical.process'))

    TestbenchGenerator().generate(
        testbench_path, output_path, 'netlist_faulted.sub', process_abs,
        original_netlist_filename='FILTER.sub'
    )

    with open(output_path, 'r') as handle:
        lines = handle.read().splitlines()

    assert '.INCLUDE netlist_faulted.sub' in lines
    assert not any('FILTER.sub' in line for line in lines), (
        "L'include original de FILTER.sub ne doit plus apparaitre, "
        "seule la version fautee doit rester."
    )
    assert any(
        line.startswith('.INCLUDE') and 'OPAMP1.sub' in line and
        os.path.isabs(line.split(None, 1)[1])
        for line in lines
    ), "OPAMP1.sub doit rester une dependance intacte, en chemin absolu."
