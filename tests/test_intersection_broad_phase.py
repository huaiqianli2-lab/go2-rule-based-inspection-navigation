import unittest
import numpy as np
from tools.route_intersections import crossing_pairs

def original(first,second=None):
 p=np.asarray(first,float)[:,:2];q=p if second is None else np.asarray(second,float)[:,:2];same=second is None;out=[]
 cross=lambda x,y:x[...,0]*y[...,1]-x[...,1]*y[...,0]
 for i in range(0,len(p)-1,256):
  a=p[i:i+256];b=p[i+1:i+257];a=a[:len(b)]
  for j in range(i if same else 0,len(q)-1,256):
   c=q[j:j+256];d=q[j+1:j+257];c=c[:len(d)];ab=b-a;cd=d-c
   eps=1e-10*np.maximum(1.,np.linalg.norm(ab,axis=1)[:,None]*np.linalg.norm(cd,axis=1)[None,:])
   x=cross(ab[:,None,:],c[None,:,:]-a[:,None,:]);y=cross(ab[:,None,:],d[None,:,:]-a[:,None,:]);u=cross(cd[None,:,:],a[:,None,:]-c[None,:,:]);v=cross(cd[None,:,:],b[:,None,:]-c[None,:,:])
   good=(((x>eps)&(y<-eps))|((x<-eps)&(y>eps)))&(((u>eps)&(v<-eps))|((u<-eps)&(v>eps)))
   if same:good &= np.arange(j,j+len(c))[None,:]>np.arange(i,i+len(a))[:,None]+1
   out.extend((i+int(r),j+int(c))for r,c in zip(*np.where(good)))
 return out

class IntersectionBroadPhaseTests(unittest.TestCase):
 def test_original_predicate_and_order_on_random_mixed_lengths_and_coordinates(self):
  rng=np.random.default_rng(20261018)
  for count,offset,scale in [(50,0,1),(530,0,1),(100,1e6,.001),(100,-1e7,1e3),(20,0,0)]:
   a=np.cumsum(rng.normal(size=(count,2)),axis=0)*scale+offset;b=np.cumsum(rng.normal(size=(count+7,2)),axis=0)*scale+offset
   self.assertEqual(crossing_pairs(a),original(a));self.assertEqual(crossing_pairs(a,b),original(a,b))
 def test_pathological_long_overlapping_boxes_use_bounded_fallback(self):
  a=np.tile([[0.,0.],[100.,100.],[0.,100.],[100.,0.]],(140,1))
  self.assertEqual(crossing_pairs(a),original(a))
 def test_shared_endpoints_retrace_degenerate_and_invalid_inputs(self):
  for p in [np.array([[0,0],[1,1],[1,1],[0,1],[1,0]]),np.array([[0,0],[1,0],[0,0],[2,0]])]:self.assertEqual(crossing_pairs(p),original(p))
  with self.assertRaises(ValueError):crossing_pairs([[0,0],[float('nan'),1]])
