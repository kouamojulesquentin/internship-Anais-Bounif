class FaultCollapser(object):
    def collapse(self, faults):
        kept = []
        seen = {}

        for fault in faults:
            key = self._key(fault)
            if key not in seen:
                seen[key] = fault
                kept.append(fault)
            else:
                seen[key].weight += fault.weight
                seen[key].metadata['collapsed_extra'] = (
                    seen[key].metadata.get('collapsed_extra', 0) + 1
                )
        return kept

    def _key(self, fault):
        if fault.fault_type == 'SHORT':
            # Short structurel entre mêmes noeuds: un seul défaut représentatif.
            return ('SHORT', tuple(sorted(fault.nodes)))

        return (
            fault.fault_type, fault.component_name,
            fault.subtype, tuple(fault.nodes)
        )
