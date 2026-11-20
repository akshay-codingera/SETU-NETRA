python -c "
import json, torch, os, sys
import numpy as np
from scipy import stats

sys.path.insert(0, 'src')
from setu_netra.policy.cm_rp import CMRPPredictor, StrategyAction
from setu_netra.pipeline.integrated_pipeline import IntegratedSetuNetraPipeline
from setu_netra.evidence.er_sp import ERSPClassifier, ERClass, compute_pair_interaction_features
from setu_netra.qa.domain_router import classify_domain, QuestionDomain

# Load eval suite
eval_suite = []
with open('training/datasets/SETU-CM/splits/test_in_domain.jsonl') as f:
    eval_suite.extend([json.loads(l) for l in f if l.strip()])
with open('training/datasets/SETU-CM/splits/test.jsonl') as f:
    eval_suite.extend([json.loads(l) for l in f if l.strip()][:40])

print(f'Eval suite loaded: {len(eval_suite)} queries')

pipe = IntegratedSetuNetraPipeline()
cm_pred = CMRPPredictor(checkpoint_path='models/policy/cm_rp_v2.pt')

c4_correct = []
c6_grounded_correct = []
c6_place_correct = []

for rec in eval_suite:
    q = rec['question']
    exp = rec['expected_action']
    is_abs_exp = (exp == StrategyAction.ABSTAIN.value)
    
    feat_old = rec.get('context_features', [])
    q_emb = np.array(feat_old[:384], dtype=np.float32) if len(feat_old) >= 384 else None

    # C4
    res_c4 = cm_pred.select_strategy(q, q_emb=q_emb, er_probs=[0.2]*5, use_fallback=False)
    act_c4 = res_c4['selected_action']
    c4_c = (act_c4 == exp)
    c4_correct.append(c4_c)

    # C6 Grounded
    res_c6g = pipe.process_inquiry(q, retrieved_passages=[f'Evidence passage containing key factual premises for: {q}'], q_emb=q_emb)
    act_c6g = res_c6g.selected_action
    is_abs_c6g = (act_c6g == StrategyAction.ABSTAIN.value) or (res_c6g.er_sufficiency_label in ('CONTRADICTORY', 'UNVERIFIABLE'))
    if is_abs_c6g:
        c6g_c = is_abs_exp
    else:
        c6g_c = (act_c6g == exp)
    c6_grounded_correct.append(c6g_c)

    # C6 Placeholder
    res_c6p = pipe.process_inquiry(q, retrieved_passages=['Sample document passage context'], q_emb=q_emb)
    act_c6p = res_c6p.selected_action
    is_abs_c6p = res_c6p.is_abstention
    if is_abs_c6p:
        c6p_c = is_abs_exp
    else:
        c6p_c = (act_c6p == exp)
    c6_place_correct.append(c6p_c)

c4_arr = np.array(c4_correct)
c6g_arr = np.array(c6_grounded_correct)
c6p_arr = np.array(c6_place_correct)

print(f'C4 accuracy: {c4_arr.mean():.4f} ({c4_arr.sum()}/{len(c4_arr)})')
print(f'C6 Grounded accuracy: {c6g_arr.mean():.4f} ({c6g_arr.sum()}/{len(c6g_arr)})')
print(f'C6 Placeholder accuracy: {c6p_arr.mean():.4f} ({c6p_arr.sum()}/{len(c6p_arr)})')

# McNemar test C4 vs C6 Grounded
# n11: both correct, n10: C4 correct C6g wrong, n01: C4 wrong C6g correct, n00: both wrong
n11 = int(np.sum((c4_arr == True) & (c6g_arr == True)))
n10 = int(np.sum((c4_arr == True) & (c6g_arr == False)))
n01 = int(np.sum((c4_arr == False) & (c6g_arr == True)))
n00 = int(np.sum((c4_arr == False) & (c6g_arr == False)))

print(f'Contingency table (C4 vs C6_Grounded): n11={n11}, n10={n10}, n01={n01}, n00={n00}')

# Exact binomial test for McNemar:
# b = n10, c = n01
b, c = n10, n01
if b + c > 0:
    binom_p = stats.binomtest(c, b + c, 0.5).pvalue
    chi2_cc = ((abs(b - c) - 1)**2) / (b + c)
    chi2_p = stats.chi2.sf(chi2_cc, df=1)
    print(f'McNemar chi2 (with CC): {chi2_cc:.4f}, p={chi2_p:.6f}')
    print(f'Exact Binomial p-value: {binom_p:.6f}')
else:
    print('No discordant pairs')
"