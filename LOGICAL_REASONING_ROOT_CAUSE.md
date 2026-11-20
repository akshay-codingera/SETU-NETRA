# Root-Cause Investigation: Handwritten Logical Reasoning Ingestion & Evaluation

**Document Version:** 1.0.0  
**Target Ingestion:** `quest8.png` (Handwritten Categorical Syllogism Inquiry)  
**System Component:** `setu_netra.qa.domain_router`, `engine`, `question_extractor`  
**Date:** November 12, 2026  

---

## 1. Problem Statement & Failure Analysis

When handwritten syllogism image `quest8.png` was uploaded to SETU-NETRA, the application exhibited two major architectural failures:

1. **Domain Misclassification:**
   The question was categorized as `DOCUMENT_QA` because the domain router only recognized keywords for `ARITHMETIC`, `SQL`, and `MATHEMATICS`. As a result, the system attempted to execute hybrid vector retrieval (`self.retriever.retrieve(...)`) against uploaded document chunks.
2. **Epistemic Inconsistency & Insufficient Evidence Rejection:**
   Because a handwritten syllogism is a self-contained deductive thought problem rather than an empirical inquiry against an external corporate docket, the vector database returned zero relevant passages. The system consequently rejected the inquiry with:
   ```text
   UNSUPPORTED (Insufficient evidence)
   ```
   Alternatively, when forced through model generation without deductive constraints, generative LLMs often hallucinated invalid syllogistic conclusions (e.g. committing the fallacy of the undistributed middle term).

---

## 2. Mathematical Diagnosis: Categorical Syllogism Entailment

**Extracted Premises from `quest8.png`:**
1. $P_1$: *"All programmers are logical"*
   $$\forall x\, (P(x) \to L(x)) \iff P \subseteq L$$
2. $P_2$: *"Some logical people are creative"*
   $$\exists x\, (L(x) \land C(x)) \iff L \cap C \neq \emptyset$$
3. $P_3$: *"No creative person is lazy"*
   $$\forall x\, (C(x) \to \neg Z(x)) \iff C \cap Z = \emptyset$$

**Candidate Conclusions:**
- **Option A:** *"Some programmers are creative"* ($P \cap C \neq \emptyset$)
- **Option B:** *"No programmer is lazy"* ($P \cap Z = \emptyset$)
- **Option C:** *"Some logical people may be programmers"* (Modal possibility)
- **Option D:** *"All creative people are programmers"* ($C \subseteq P$)

### The Fallacy of the Undistributed Middle
A naive solver often reasons:
*"Programmers are logical. Some logical people are creative. Therefore, some programmers are creative."*
This is the classical formal fallacy of the **Undistributed Middle Term** ($L$). The sub-class of logical people who are creative ($L \cap C$) is not guaranteed to overlap with the sub-class of logical people who are programmers ($P \subseteq L$).

### Countermodel Proof against Options A, B, and D:
Let the domain of discourse be finite universe $U = \{1, 2, 3\}$:
- $P = \{1\}$ (Programmer 1)
- $L = \{1, 2\}$ (Logical persons 1 and 2)
- $C = \{2\}$ (Creative person 2)
- $Z = \{1, 3\}$ (Lazy persons 1 and 3)

Let us verify all three premises in this model:
1. $P \subseteq L$: $\{1\} \subseteq \{1, 2\}$. **(Holds)**
2. $L \cap C \neq \emptyset$: $\{1, 2\} \cap \{2\} = \{2\} \neq \emptyset$. **(Holds)**
3. $C \cap Z = \emptyset$: $\{2\} \cap \{1, 3\} = \emptyset$. **(Holds)**

Now check candidate conclusions:
- **Option A ($P \cap C \neq \emptyset$):** $\{1\} \cap \{2\} = \emptyset$. **False in model.** (Invalid entailment)
- **Option B ($P \cap Z = \emptyset$):** $\{1\} \cap \{1, 3\} = \{1\} \neq \emptyset$. **False in model.** (Invalid entailment)
- **Option D ($C \subseteq P$):** $\{2\} \subseteq \{1\}$ is False. **False in model.** (Invalid entailment)

### Resolution for Option C:
Option C asserts: *"Some logical people may be programmers."*
The modal auxiliary **"may be"** denotes epistemic possibility (satisfiability in at least one valid model).
Because Premise 1 guarantees $P \subseteq L$, any model in which $P \neq \emptyset$ contains an individual who is both logical and a programmer ($L \cap P = P \neq \emptyset$). Thus, Option C is a consistent modal truth across all non-trivial models.

---

## 3. Structural Remediation

1. Introduce distinct domain `QuestionDomain.LOGICAL_REASONING`.
2. Implement model-theoretic countermodel engine evaluating deductive validity across four truth statuses:
   - `DEFINITELY_TRUE`
   - `POSSIBLY_TRUE`
   - `DEFINITELY_FALSE`
   - `INDETERMINATE`
3. Enforce epistemic status `LOGIC_VERIFIED` with `citations = []`, preventing false retrieval lookups and eliminating hallucinated empty citation cards.
