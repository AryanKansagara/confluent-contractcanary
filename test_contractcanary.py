import unittest
from contractcanary import experiment, migrate, minimize, demo, Unsupported

class Contracts(unittest.TestCase):
    def event(self, **kwargs):
        return dict(dict(amount=10,currency='USD',discount=2,customer_id='alice'),**kwargs)
    def test_safe_currency_identity_discount_roundtrip(self):
        for currency in ('USD','JPY'):
            self.assertEqual(experiment(self.event(currency=currency),[1,2,3,2,1])['status'],'pass')
    def test_structural_compatibility_hides_changed_units(self):
        r=experiment(self.event(),[1,2],migrations=False)
        self.assertTrue(r['structural_pass']); self.assertIn('net_minor',r['violations'])
    def test_currency_specific_counterexample(self):
        self.assertEqual(experiment(self.event(),[1,2],defect='units')['status'],'pass')
        self.assertEqual(experiment(self.event(currency='JPY'),[1,2],defect='units')['status'],'violation')
    def test_rename_loses_identity_and_roundtrip_loses_discount(self):
        self.assertIn('customer',experiment(self.event(),[1,2,3],defect='identity')['violations'])
        self.assertIn('net_minor',experiment(self.event(),[1,2,1],defect='discount')['violations'])
    def test_unsupported_client_direct_edge_and_lossy_downcast(self):
        self.assertEqual(experiment(self.event(),[1,2],client='protobuf')['status'],'unsupported')
        self.assertEqual(experiment(self.event(),[1,3])['status'],'unsupported')
        self.assertEqual(experiment(self.event(amount=1,discount=None),[2,1])['status'],'unsupported')
        self.assertEqual(experiment(self.event(),[1,2],client='json-no-rules')['status'],'unsupported')
    def test_minimizer_preserves_witness(self):
        event=dict(self.event(currency='JPY'),debug='drop')
        reduced=minimize(event,[1,2],defect='units')
        self.assertNotIn('debug',reduced['event']); self.assertEqual(reduced['result']['status'],'violation')
        self.assertLess(len(str(reduced['event'])),len(str(event)))
    def test_reject_bool_money_invalid_path_currency(self):
        for value in (True,'10',None):
            with self.assertRaises(ValueError):experiment(self.event(amount=value),[1,2])
        with self.assertRaises(Unsupported):experiment(self.event(currency='XYZ'),[1])
        with self.assertRaises(ValueError):experiment(self.event(),[])
    def test_direct_migration_rejects_invalid_exact_version_types(self):
        for source, target in ((1,0),(1,2.0),(True,2),(1,True),(None,2),(1,4)):
            with self.subTest(source=source,target=target),self.assertRaises(Unsupported):
                migrate(self.event(),source,target)
    def test_demo_safe_controls(self):
        result=demo(); self.assertEqual(result['safe_failures'],0)
        self.assertGreater(result['semantic_violations'],0); self.assertGreater(result['structural_baseline_misses'],0)

if __name__=='__main__':unittest.main()
