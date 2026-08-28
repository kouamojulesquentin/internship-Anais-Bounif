import os


class TestbenchGenerator(object):
    def generate(self, source_testbench, output_testbench,
                 faulty_netlist_path, process_file_path,
                 original_netlist_filename=None):
        with open(source_testbench, 'r', encoding='utf-8', errors='replace') as handle:
            lines = handle.read().splitlines()

        source_dir = os.path.dirname(os.path.abspath(source_testbench))
        target_basename = (
            os.path.basename(original_netlist_filename).lower()
            if original_netlist_filename else None
        )

        output = []
        netlist_replaced = False
        process_inserted = False

        for line in lines:
            stripped = line.strip()
            low = stripped.lower()

            is_include_sub = (
                '.include' in low and '.sub' in low and 'primitive.sub' not in low
            )

            if is_include_sub and not netlist_replaced:
                # Si on connait le nom du fichier netlist d'origine (cas des
                # testbenchs hierarchiques avec plusieurs .sub, ex: FILTER qui
                # inclut aussi OPAMP1.sub), on ne remplace QUE la ligne qui
                # reference precisement ce fichier — jamais la premiere ligne
                # .sub venue, qui pourrait etre une dependance a garder intacte.
                if target_basename is not None:
                    tokens = stripped.split(None, 1)
                    ref_basename = (
                        os.path.basename(tokens[1].strip()).lower()
                        if len(tokens) == 2 else ''
                    )
                    if ref_basename == target_basename:
                        output.append('.INCLUDE {}'.format(faulty_netlist_path))
                        netlist_replaced = True
                        continue
                    # Ce n'est pas le bon fichier .sub (ex: OPAMP1.sub, une
                    # dependance) : on le laisse traiter plus bas comme un
                    # .INCLUDE normal (absolutisation de chemin).
                else:
                    output.append('.INCLUDE {}'.format(faulty_netlist_path))
                    netlist_replaced = True
                    continue

            if '.include' in low and '.process' in low:
                output.append(line if stripped.startswith('*') else '*' + line)
                continue

            if (
                not process_inserted and
                (
                    low.startswith('.tran') or low.startswith('.ac') or
                    low.startswith('.dc') or low.startswith('.noise') or
                    low.startswith('.end')
                )
            ):
                output.append('.INCLUDE {}'.format(process_file_path))
                process_inserted = True

            # Toute autre ligne .INCLUDE (ex: PRIMITIVE.sub, ou une dependance
            # comme OPAMP1.sub) est reecrite en chemin absolu par rapport au
            # testbench d'origine, car le fichier genere vit dans un
            # sous-dossier par corner/faute et un chemin relatif casserait la
            # resolution Spectre.
            if stripped.upper().startswith('.INCLUDE') and not stripped.startswith('*'):
                tokens = stripped.split(None, 1)
                if len(tokens) == 2:
                    ref = tokens[1].strip()
                    if not os.path.isabs(ref):
                        abs_ref = os.path.normpath(os.path.join(source_dir, ref))
                        line = '.INCLUDE {}'.format(abs_ref)

            output.append(line)

        if not netlist_replaced:
            raise ValueError("Include du fichier .sub introuvable dans le testbench.")

        if not process_inserted:
            output.append('.INCLUDE {}'.format(process_file_path))

        folder = os.path.dirname(output_testbench)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)

        with open(output_testbench, 'w', encoding='utf-8', errors='replace') as handle:
            handle.write('\n'.join(output) + '\n')

        return output_testbench
