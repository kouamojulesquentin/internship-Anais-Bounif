from fault_injection.simulation.mt0_parser import parse_mt0, parse_all_records


def test_multi_record_mt0(tmpdir):
    path = str(tmpdir.join('sample.mt0'))
    with open(path, 'w') as handle:
        handle.write('$ Simulator: spectre\n.title test\ngain temper alter#\n1.0 27 1\n0.8 27 2\n')
    records = parse_mt0(path)
    assert len(records) == 2
    assert records[0]['gain'] == 1.0
    assert records[1]['gain'] == 0.8


def test_parse_all_records_merges_across_analysis_files(tmpdir):
    workdir = tmpdir.mkdir('run')
    tb = str(workdir.join('job.circuit'))

    with open(str(workdir.join('job.mt0')), 'w') as handle:
        handle.write(
            '$ Simulator: Spectre\n.title x\n'
            'vout rout temper alter#\n'
            '1.19 40.0 27 1\n'
        )
    with open(str(workdir.join('job.mt1')), 'w') as handle:
        handle.write(
            '$ Simulator: Spectre\n.title x\n'
            'psrr_db_1k temper alter#\n'
            '-44.0 27 2\n'
        )

    records = parse_all_records(tb)

    assert len(records) == 1
    record = records[0]
    assert record['vout'] == 1.19
    assert record['rout'] == 40.0
    assert record['psrr_db_1k'] == -44.0
