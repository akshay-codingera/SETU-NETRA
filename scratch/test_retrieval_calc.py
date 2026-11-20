import sys
sys.path.insert(0, "src")
import json
from setu_netra.store.sqlite_store import SQLiteDocumentStore
from setu_netra.semantic.embeddings.neural_engine import NeuralSentenceEmbeddingEngine
from setu_netra.retrieval.document_retriever import DocumentRetriever

store = SQLiteDocumentStore("output/e2e_verify/e2e_netra.db")
engine = NeuralSentenceEmbeddingEngine()
retriever = DocumentRetriever(store=store, embedding_engine=engine)

with open("benchmarks/datasets/qa_eval_dataset.json") as f:
    dataset = json.load(f)

print("=== Approach A: Document-Level (Unique Set Intersection) ===")
for k in [1, 3, 5, 10]:
    recs, precs = [], []
    for item in dataset:
        target = item.get("document_id")
        if not target:
            continue
        passages = retriever.retrieve(query=item["question"], top_k=k)
        ret_docs = set(p.doc_id for p in passages)
        rel_docs = {target}
        hits = len(ret_docs & rel_docs)
        recs.append(hits / len(rel_docs))
        precs.append(hits / k)
    print(f"k={k}: Recall@{k} = {sum(recs)/len(recs):.4f}, Precision@{k} = {sum(precs)/len(precs):.4f}")

print("\n=== Approach B: Passage-Level (Doc + Page + Block ID) ===")
for k in [1, 3, 5, 10]:
    recs, precs = [], []
    for item in dataset:
        target_doc = item.get("document_id")
        if not target_doc:
            continue
        target_passage = f"{target_doc}:p{item.get('page_number')}:b{item.get('block_id')}"
        passages = retriever.retrieve(query=item["question"], top_k=k)
        ret_passages = [f"{p.doc_id}:p{p.page_number}:b{p.block_id}" for p in passages]
        rel_passages = {target_passage}
        hits = len(set(ret_passages) & rel_passages)
        recs.append(hits / len(rel_passages))
        precs.append(hits / k)
    print(f"k={k}: Recall@{k} = {sum(recs)/len(recs):.4f}, Precision@{k} = {sum(precs)/len(precs):.4f}")
