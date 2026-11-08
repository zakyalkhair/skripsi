import pandas as pd, itertools, json, re
from rapidfuzz import fuzz
d=pd.read_parquet('data/interim/dedup.parquet')
txt=d.set_index('tweet_id').text_clean
reps=d[(d.cluster_size>1)&(d.is_representatif==True)]
rows=[]
for _,r in reps.iterrows():
    ids=list(r.member_tweet_ids); t=[txt.get(i,'') for i in ids]
    mn=100; 
    n=len(t)
    # untuk gugus besar, pairwise penuh tetap ok (<=238)
    for a,b in itertools.combinations(range(n),2):
        s=fuzz.ratio(t[a],t[b]); mn=min(mn,s)
    # rerata ke wakil
    ri=ids.index(r.tweet_id) if r.tweet_id in ids else 0
    rows.append(dict(cluster_id=r.cluster_id,size=n,min_pair=mn,wakil=r.tweet_id,contoh=txt.get(r.tweet_id,'')[:100]))
a=pd.DataFrame(rows); a.to_csv('reports/audit_gugus_dedup_8nov.csv',index=False)
print(len(a)); print(a.min_pair.describe())
for th in (85,80,75,70,60):
    print('min_pair <',th,(a.min_pair<th).sum())
print(a[a.min_pair<75].sort_values('size',ascending=False).head(15).to_string())
print(a.sort_values('size',ascending=False).head(12)[['size','min_pair','contoh']].to_string())
