import numpy as np
from string import ascii_uppercase, ascii_lowercase
import urllib.parse
import urllib.request

def parse_a3m(a3m_lines, filter_qid=0.15, filter_cov=0.5):
  seq,lab = [],[]
  is_first = True
  for line in a3m_lines.splitlines():
    if line[0] == '>':
      label = line.strip()[1:]
      is_incl = True
      if is_first: # include first sequence (query)
        is_first = False
        lab.append(label)
        continue
      if "UniRef" in label:
        code = label.split()[0].split('-')[0]
        if "_UPI" in code: # UniParc identifier -- exclude
          is_incl = False
          continue
      else:
        is_incl = False
        continue
      lab.append(code)
    else:
      if is_incl:
        seq.append(line.rstrip())
      else:
        continue

  deletion_matrix = []
  for msa_sequence in seq:
    deletion_vec = []
    deletion_count = 0
    for j in msa_sequence:
      if j.islower():
        deletion_count += 1
      else:
        deletion_vec.append(deletion_count)
        deletion_count = 0
    deletion_matrix.append(deletion_vec)

  # Make the MSA matrix out of aligned (deletion-free) sequences.
  deletion_table = str.maketrans('', '', ascii_lowercase)
  aligned_sequences = [s.translate(deletion_table) for s in seq]

  #Filter
  if len(aligned_sequences) > 1 and (filter_cov < 1 or filter_qid < 1):
    _msa,_mtx,_lab = [],[],[]
    ref_seq = np.array(list(aligned_sequences[0]))
    for s,m,l in zip(aligned_sequences[1:],deletion_matrix[1:],lab[1:]):
      tar_seq = np.array(list(s))
      cov = (tar_seq != "-").mean()
      qid = (ref_seq == tar_seq).mean()
      if cov > filter_cov and qid > filter_qid:
        _msa.append(s)
        _mtx.append(m)
        _lab.append(l)
    print(f"found {len(_lab)}")    
    return _msa, _mtx, _lab
  else:
    print(f"found {len(aligned_sequences) - 1}")    
    return aligned_sequences[1:], deletion_matrix[1:], lab[1:]

def get_uni_jackhmmer(msa, mtx, lab, filter_qid=0.15, filter_cov=0.5):
  '''filter entries to uniprot'''
  lab_,msa_,mtx_ = [],[],[]
  ref_seq = np.array(list(msa[0]))
  for l,s,x in zip(lab[1:],msa[1:],mtx[1:]):
    if l.startswith("UniRef"):
      l = l.split("/")[0]
      if "_UPI" not in l:
        tar_seq = np.array(list(s))
        cov = (tar_seq != "-").mean()
        qid = (ref_seq == tar_seq).mean()
        if cov > filter_cov and qid > filter_qid:
          lab_.append(l)
          msa_.append(s)
          mtx_.append(x)
  return msa_, mtx_, lab_

def uni_num(ids):
  ########################################
  pa = {a:0 for a in ascii_uppercase}
  for a in ["O","P","Q"]: pa[a] = 1
  ma = [[{} for k in range(6)],[{} for k in range(6)]]
  for n,t in enumerate(range(10)):
    for i in [0,1]:
      for j in [0,4]: ma[i][j][str(t)] = n
  for n,t in enumerate(list(ascii_uppercase)+list(range(10))):
    for i in [0,1]:
      for j in [1,2]: ma[i][j][str(t)] = n
    ma[1][3][str(t)] = n
  for n,t in enumerate(ascii_uppercase):
    ma[0][3][str(t)] = n
    for i in [0,1]: ma[i][5][str(t)] = n
  ########################################
  nums = []
  for uni in ids:
    p = pa[uni[0]]
    tot, num = 1,0
    if len(uni) == 10:
      for n,u in enumerate(reversed(uni[-4:])):
        num += ma[p][n][u] * tot
        tot *= len(ma[p][n].keys())
    for n,u in enumerate(reversed(uni[:6])):
      num += ma[p][n][u] * tot
      tot *= len(ma[p][n].keys())
    nums.append(num)
  return nums

def map_retrieve(ids, call_uniprot=True):

  if call_uniprot:
    mode = "NF100" if "UniRef100" in ids[0] else "NF90"
    url = 'https://www.uniprot.org/uploadlists/'
    out = []
    for i in range(0,len(ids),10000):
      params = {
      'from': mode,
      'to': 'ACC',
      'format': 'tab',
      'query': " ".join(ids[i:i+10000])
      }
      data = urllib.parse.urlencode(params)
      data = data.encode('utf-8')
      req = urllib.request.Request(url, data)
      with urllib.request.urlopen(req) as f:
        response = f.read()
      out += [line.split() for line in response.decode('utf-8').splitlines()]

    # combine mapping
    mapping = {}
    for i,j in out:
      if i != "From":
        if i not in mapping:
          mapping[i] = [j]
        else:
          mapping[i].append(j)
  else:
    mapping = {}

  for i in ids:
    if i not in mapping:
      mapping[i] = [i.split("_")[1]]
  
  return mapping

def hash_it(_seq, _lab, _mtx, call_uniprot=True):
  if _seq is None or _lab is None:
    _seq, _lab = parse_a3m(a3m_lines)

  _lab_to_seq = {L:S for L,S in zip(_lab,_seq)}
  _lab_to_mtx = {L:M for L,M in zip(_lab,_mtx)}
  
  # call uniprot
  _lab_to_uni = map_retrieve(_lab, call_uniprot=call_uniprot)
  
  _uni_to_lab = {}
  for L,U in _lab_to_uni.items():
    for u in U: _uni_to_lab[u] = L

  _uni,__lab = [],[]
  for U,L in _uni_to_lab.items():
    _uni.append(U)
    __lab.append(L)
  
  _hash = uni_num(_uni)
  _uni_to_hash = {u:h for u,h in zip(_uni,_hash)}
  _hash_to_lab = {h:l for h,l in zip(_hash,__lab)}

  _lab_to_hash = {}
  for L,U in _lab_to_uni.items():
    _lab_to_hash[L] = []
    for u in U: _lab_to_hash[L].append(_uni_to_hash[u])

  return {"_lab_to_seq":_lab_to_seq,
          "_lab_to_mtx":_lab_to_mtx,
          "_lab_to_hash":_lab_to_hash,
          "_hash_to_lab":_hash_to_lab}

def stitch(_hash_a,_hash_b, stitch_min=1, stitch_max=20, filter_id=0.9):
  _seq_a, _seq_b = [],[]
  _mtx_a, _mtx_b = [],[]
  if filter_id < 1: _seq = []
  for l_a,h_a in _hash_a["_lab_to_hash"].items():
    h_a = np.asarray(h_a)
    h_b = np.asarray(list(_hash_b["_hash_to_lab"].keys()))
    match = np.abs(h_a[:,None]-h_b[None,:]).min(0)
    match_min = match.min()
    if match_min >= stitch_min and match_min <= stitch_max:
      l_b = _hash_b["_hash_to_lab"][h_b[match.argmin()]]
      _seq_a.append(_hash_a["_lab_to_seq"][l_a])
      _seq_b.append(_hash_b["_lab_to_seq"][l_b])
      _mtx_a.append(_hash_a["_lab_to_mtx"][l_a])
      _mtx_b.append(_hash_b["_lab_to_mtx"][l_b])
      if filter_id < 1: _seq.append(_seq_a[-1]+_seq_b[-1])
  if filter_id < 1: 
    _seq = np.asarray([list(s) for s in _seq])
    ok = np.ones(_seq.shape[0])
    for n in range(_seq.shape[0]-1):
      if ok[n]:
        ident = (_seq[n] == _seq[(n+1):]).mean(-1)
        ok[(n+1):] = (ident <= filter_id)
    
    ok = np.where(ok)[0]
    filt = lambda x: [x[i] for i in ok]
    return filt(_seq_a),filt(_seq_b),filt(_mtx_a),filt(_mtx_b)
  else:
    return _seq_a, _seq_b, _mtx_a, _mtx_b