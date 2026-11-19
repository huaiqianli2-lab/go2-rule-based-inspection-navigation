"""Proper actual-route crossings in bounded blocks; separate from legacy metric."""
import numpy as np


def iter_crossing_pairs(first,second=None):
    p=np.asarray(first,float);q=p if second is None else np.asarray(second,float)
    same=second is None
    if min(len(p),len(q))<2:return
    if p.ndim!=2 or q.ndim!=2 or min(p.shape[1],q.shape[1])<2 or not np.isfinite(p).all() or not np.isfinite(q).all():raise ValueError('路线坐标无效')
    p=p[:,:2];q=q[:,:2]
    from scipy.spatial import cKDTree
    a_all=p[:-1];b_all=p[1:];c_all=q[:-1];d_all=q[1:]
    ab_all=b_all-a_all;cd_all=d_all-c_all
    plen=np.linalg.norm(ab_all,axis=1);qlen=np.linalg.norm(cd_all,axis=1)
    pc=(a_all+b_all)/2;qc=(c_all+d_all)/2;tree=cKDTree(qc)
    padding=1e-9*max(1.,float(np.abs(p).max()),float(np.abs(q).max()))
    radius=plen/2+float(qlen.max())/2+padding
    def cross(x,y):return x[...,0]*y[...,1]-x[...,1]*y[...,0]
    def checked(rows,cols):
        a=a_all[rows];b=b_all[rows];c=c_all[cols];d=d_all[cols]
        # Conservative broad phase only; the SAME four signed cross products
        # and tolerances below remain the exact final predicate.
        boxes=((np.maximum(a,b)+padding>=np.minimum(c,d)).all(1)&
               (np.maximum(c,d)+padding>=np.minimum(a,b)).all(1))
        rows=rows[boxes];cols=cols[boxes]
        a=a[boxes];b=b[boxes];c=c[boxes];d=d[boxes]
        ab=b-a;cd=d-c
        eps=1e-10*np.maximum(1.,plen[rows]*qlen[cols])
        x=cross(ab,c-a);y=cross(ab,d-a);u=cross(cd,a-c);v=cross(cd,b-c)
        proper=(((x>eps)&(y<-eps))|((x<-eps)&(y>eps)))&(((u>eps)&(v<-eps))|((u<-eps)&(v>eps)))
        for i,j in zip(rows[proper],cols[proper]):yield int(i),int(j)
    for first in range(0,len(pc),256):
        last=min(first+256,len(pc))
        counts=tree.query_ball_point(pc[first:last],radius[first:last],return_length=True,workers=1)
        if counts.sum()>262144:
            # Pathological long/dense segments retain bounded original blocks.
            for j in range(first if same else 0,len(qc),256):
                rows,cols=np.meshgrid(np.arange(first,last),np.arange(j,min(j+256,len(qc))),indexing='ij')
                rows=rows.ravel();cols=cols.ravel()
                use=cols>rows+1 if same else np.ones(len(rows),bool)
                yield from checked(rows[use],cols[use])
            continue
        neighbours=tree.query_ball_point(pc[first:last],radius[first:last],workers=1)
        rows=np.repeat(np.arange(first,last),[len(v) for v in neighbours])
        cols=np.concatenate(neighbours).astype(int) if counts.sum() else np.empty(0,int)
        use=cols>rows+1 if same else np.ones(len(rows),bool)
        rows=rows[use];cols=cols[use]
        # Preserve the old 256x256 block ordering for deterministic callers.
        order=np.lexsort((cols,rows,cols//256))
        yield from checked(rows[order],cols[order])


def crossing_pairs(first,second=None):return list(iter_crossing_pairs(first,second))


def proper_crossings(points):return sum(1 for _ in iter_crossing_pairs(points))


def transverse_events(points):
    """Crossing locations including crossings split at polyline vertices.

    Four alternating outgoing rays define a transverse crossing. Merely
    inserting vertices at an X cannot turn it into zero. Shared road forks
    and collinear retracing are separate from transverse crossings.
    """
    raw=np.asarray(points,float)
    if len(raw)<2:return []
    if raw.ndim!=2 or raw.shape[1]<2 or not np.isfinite(raw).all():raise ValueError('路线坐标无效')
    p=[raw[0,:2]]
    for q in raw[1:,:2]:
        if np.linalg.norm(q-p[-1])>1e-8:p.append(q)
    p=np.asarray(p);closed=len(p)>2 and np.linalg.norm(p[0]-p[-1])<1e-8
    count=len(p)-1 if closed else len(p);events={}
    def record(q,**detail):
        key=tuple(np.round(q,7));events.setdefault(key,dict(xy=[float(x)for x in q],**detail))
    def cross(a,b):return a[0]*b[1]-a[1]*b[0]
    for i,j in iter_crossing_pairs(p):
        a,b=p[i],p[i+1];c,d=p[j],p[j+1];ab=b-a;cd=d-c
        q=a+ab*(cross(c-a,cd)/cross(ab,cd));record(q,segments=[i,j],kind='segment_interiors')
    def rays(k):
        k=k%count
        if not closed and k in (0,count-1):return None
        center=p[k];return [p[(k-1)%count]-center,p[(k+1)%count]-center]
    def alternating(a,b):
        if a is None or b is None:return False
        tagged=[(float(np.arctan2(v[1],v[0]))%(2*np.pi),tag)for tag,vs in enumerate((a,b))for v in vs]
        tagged.sort()
        return all((tagged[(i+1)%4][0]-tagged[i][0])%(2*np.pi)>1e-7 and tagged[i][1]!=tagged[(i+1)%4][1] for i in range(4))
    if len(p)<3:return list(events.values())
    a=p[:-1];b=p[1:];delta=b-a;length2=np.einsum('ij,ij->i',delta,delta)
    for k,q in enumerate(p[:count]):
        ar=rays(k)
        if ar is None:continue
        t=np.clip(np.einsum('ij,ij->i',q-a,delta)/length2,0,1)
        distance=np.linalg.norm(a+t[:,None]*delta-q,axis=1)
        for j in np.flatnonzero(distance<=1e-8):
            if j in (k-1,k) or closed and k==0 and j==len(a)-1:continue
            if np.linalg.norm(q-a[j])<=1e-8:br=rays(j)
            elif np.linalg.norm(q-b[j])<=1e-8:br=rays(j+1)
            else:br=[a[j]-q,b[j]-q]
            if alternating(ar,br):record(q,vertex=k,segment=int(j),kind='vertex_invariant')
    return list(events.values())


def transverse_crossings(points):return len(transverse_events(points))


def repeated_length(points):
    """Extra travel on EXACT collinear overlapping segments, not near lanes."""
    p=np.asarray(points,float)
    if len(p)<2:return 0.
    if p.ndim!=2 or p.shape[1]<2 or not np.isfinite(p).all():raise ValueError('路线坐标无效')
    groups={};total=0.
    for a,b in zip(p[:,:2],p[1:,:2]):
        v=b-a;length=float(np.linalg.norm(v))
        if length<=1e-8:continue
        total+=length;u=v/length
        if u[0]<-1e-12 or abs(u[0])<=1e-12 and u[1]<0:u=-u
        normal=np.array([-u[1],u[0]]);key=(round(float(u[0]),8),round(float(u[1]),8),round(float(normal@a),7))
        groups.setdefault(key,[]).append(sorted([float(u@a),float(u@b)]))
    union=0.
    for intervals in groups.values():
        intervals.sort();start,end=intervals[0]
        for lo,hi in intervals[1:]:
            if lo<=end+1e-8:end=max(end,hi)
            else:union+=end-start;start,end=lo,hi
        union+=end-start
    return max(0.,total-union)
