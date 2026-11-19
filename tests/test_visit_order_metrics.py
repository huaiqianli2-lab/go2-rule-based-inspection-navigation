import copy
import itertools
import math
import unittest

from tools.visit_order_metrics import audit_visit_orders, limited_order_note


class VisitOrderAuditTests(unittest.TestCase):
    def metrics(self):
        D=[[0, 10, 10, 10], [10, 0, 10, 11], [10, 10, 0, 10], [10, 11, 10, 0]]
        audit=audit_visit_orders(D,loop=True,sampled_average=41)
        return dict(target_count=3,improvement_vs_random_pct=2.4,path_length_m=40,
                    random_avg_length_m=41,visit_order_audit=audit)

    def test_complete_enumeration_directed_open_and_closed(self):
        D=[[0,1,4,7],[2,0,3,6],[5,8,0,9],[10,11,12,0]]
        for loop in (False,True):
            costs=[]
            for p in itertools.permutations([1,2,3]):
                seq=[0]+list(p)+([0] if loop else [])
                costs.append(sum(D[a][b] for a,b in zip(seq,seq[1:])))
            audit=audit_visit_orders(D,loop=loop,sampled_average=sum(costs)/len(costs))
            self.assertEqual(audit['total_orders'],6)
            self.assertEqual(audit['feasible_orders'],6)
            self.assertEqual(audit['best_length_m'],min(costs))
            self.assertAlmostEqual(audit['complete_random_average_m'],sum(costs)/6)
            self.assertEqual(audit['loop'],loop)

    def test_only_proven_limited_space_gets_note(self):
        self.assertIn('场景较简单',limited_order_note(self.metrics()))
        for key,value in (('improvement_vs_random_pct',20),('path_length_m',1),('target_count',53),
                          ('random_avg_length_m',100),('random_avg_length_m',math.nan)):
            metrics=self.metrics();metrics[key]=value
            self.assertEqual(limited_order_note(metrics),'')
        metrics=self.metrics();metrics['visit_order_audit']['complete_random_average_m']=100
        self.assertEqual(limited_order_note(metrics),'')
        for key,value in (('feasible_orders',5),('total_orders',5),('schema',99),('best_length_m',math.inf)):
            metrics=self.metrics();metrics['visit_order_audit'][key]=value
            self.assertEqual(limited_order_note(metrics),'')
        self.assertEqual(limited_order_note({'target_count':4,'improvement_vs_random_pct':5}), '')

    def test_unreachable_orders_do_not_become_simple_scene(self):
        D=[[0,1,1],[1,0,math.inf],[1,1,0]]
        audit=audit_visit_orders(D,loop=True,sampled_average=3)
        self.assertEqual(audit['feasible_orders'],1)
        metrics=dict(target_count=2,path_length_m=3,random_avg_length_m=3,
                     improvement_vs_random_pct=0,visit_order_audit=audit)
        self.assertEqual(limited_order_note(metrics),'')

    def test_no_mutation_no_factorial_work_for_large_scenes(self):
        D=[[0,1],[1,0]];before=copy.deepcopy(D)
        audit=audit_visit_orders(D,loop=True,sampled_average=2)
        self.assertEqual(D,before);self.assertEqual(audit['total_orders'],1)
        self.assertIsNone(audit_visit_orders([[0]*10 for _ in range(10)],loop=True,sampled_average=1))
        self.assertIsNone(audit_visit_orders([[0]],loop=False,sampled_average=1))
        self.assertIsNone(audit_visit_orders([[0,math.inf],[math.inf,0]],loop=True,sampled_average=None))
        for D in ([[0,1],[1]],[[0,-1],[1,0]],[[0,math.nan],[1,0]]):
            with self.assertRaises(ValueError):audit_visit_orders(D,loop=True,sampled_average=1)


if __name__=='__main__':unittest.main()
