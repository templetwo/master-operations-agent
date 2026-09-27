"""Versioned snapshot controller context, without new tools or advice rules."""
import copy
import unittest
from moa.contracts import Rejected, validate_snapshot
from moa.engine import Agent, ReadTools
from moa.evidence import EvidenceStore
from moa.fixtures import fixture


def snapshot():
    value = fixture('normal')
    value.update(schema_version='1.3', profile='ess-u1-v1')
    value['source']['adapter'] = 'ess-v1'
    value['tags'] = [dict(id=tag, value=pv, unit=unit, quality='good', observed_at=value['captured_at'])
                     for tag, pv, unit in [('TIC201',150,'DEG C'), ('TIC202',40,'DEG C'), ('FIC102',60,'M3/H')]]
    value['loops'] = [dict(tag=row['id'], sp=row['value'], op=50, mode=mode, sp_unit=row['unit'], op_unit='%')
                      for row, mode in zip(value['tags'], ('AUTO','CAS','MAN'))]
    return value


class ControllerContextTests(unittest.TestCase):
    def test_versioned_context_survives_validated_read_snapshot_without_changing_legacy(self):
        value = snapshot()
        self.assertEqual(validate_snapshot(value),value)
        boundary = ReadTools(value,lambda *_:None)
        exported = boundary.call('read_snapshot',{})
        self.assertEqual([row['mode'] for row in exported['loops']], ['AUTO','CAS','MAN'])
        exported['loops'][0]['sp'] = 0
        self.assertEqual(boundary.call('read_snapshot',{})['loops'][0]['sp'],150)
        with self.assertRaises(Rejected): boundary.call('read_loop',{'tag':'TIC202'})
        legacy = copy.deepcopy(value)
        legacy['schema_version'] = '1.0'
        with self.assertRaises(Rejected): validate_snapshot(legacy)
        del legacy['loops']
        self.assertEqual(validate_snapshot(legacy),legacy)
        del value['loops']
        with self.assertRaises(Rejected): validate_snapshot(value)

    def test_context_has_exact_fields_unique_tag_bindings_finite_numbers_and_real_modes(self):
        patches = [{'mode':'REMOTE'}, {'mode':None}, {'mode':1}, {'sp':None}, {'sp':True},
                   {'op':float('inf')}, {'sp_unit':'%'}, {'op_unit':'DEG C'},
                   {'tag':'UNKNOWN'}, {'fault':'hidden'}]
        for patch in patches:
            with self.subTest(patch=patch):
                value=snapshot(); value['loops'][0].update(patch)
                with self.assertRaises(Rejected): validate_snapshot(value)
        value=snapshot(); value['loops'][0]=copy.deepcopy(value['loops'][1])
        with self.assertRaises(Rejected): validate_snapshot(value)
        value=snapshot(); value['loops'].pop()
        with self.assertRaises(Rejected): validate_snapshot(value)
        value=snapshot(); value['profile']='demo-cooling-v1'
        with self.assertRaises(Rejected): validate_snapshot(value)

    def test_context_does_not_grant_new_advice_authority_or_upgrade_uncertain_pv(self):
        store=EvidenceStore(':memory:')
        try:
            value=snapshot()
            result=Agent(store).assess(value)
            self.assertEqual(result['status'],'advisory')
            self.assertEqual([row['id'] for row in result['findings']], ['no_reported_alarms'])
            value['tags'][1].update(value=103.125,quality='uncertain')
            result=Agent(store).assess(value)
            self.assertEqual((result['status'],result['reason']),('abstain','quality'))
        finally:
            store.close()


if __name__ == '__main__': unittest.main()
