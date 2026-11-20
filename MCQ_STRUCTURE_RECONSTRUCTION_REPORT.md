# Multiple-Choice Structure Reconstruction Report

**Document Version:** 1.0.0  
**Target Ingestion:** `quest7.png`, `quest8.png`  
**Subsystems:** `setu_netra.structure.block_grouper`, `classifier`, `qa.question_extractor`  
**Date:** November 12, 2026  

---

## 1. Executive Summary

This report documents the reconstruction of multiple-choice questions (MCQs) containing multiline statements, handwritten delimiters, and multi-line SQL code blocks. The upgraded structure engine segments the complete question prompt, preserves intact clauses up to terminal question marks, and extracts all answer options without manual intervention or hardcoded patterns.

---

## 2. Ingestion & Structural Reconstruction

### 2.1 Quest 7: SQL Assessment Ingestion
In `quest7.png`, the document contains:
- One main question statement spanning 5 handwritten lines.
- Four candidate SQL queries (Options A, B, C, D) spanning 2 to 3 lines each.

#### Segmented Document Blocks:
- **Block #1 [QUESTION]:**
  ```text
  uestion
  which of the following SQL query Correctly selects the
  students whose age is greater than 10 _ and shous the
  result groubed by theix Groub (i.e., number of students in
  each Groub) ?
  ```
- **Block #2 [OPTION A - SQL CODE]:**
  ```sql
  A SELECT Grroup , COUNT ( *) FROM Student
  WHERE Age > 10
  GRoUp BY Group ;
  ```
- **Block #3 [OPTION B - SQL CODE]:**
  ```sql
  B SELECT * FROM Student
  WHERE Age 7 10 AND Group ;
  ```
- **Block #4 [OPTION C - SQL CODE]:**
  ```sql
  SELECT Group , COUNT ( Group ) FROM Student
  GROUp BY Grroup
  HAVING Age 7 10 ;
  ```
  *(Note: Handwritten "C" was faint; sequential reconstructor inferred label C between B and D based on distinct SQL statement query boundaries and semicolon termination).*
- **Block #5 [OPTION D - SQL CODE]:**
  ```sql
  D SELECT Group COUNT( *) FROM Student
  WKERE Age > 10
  ORDER BY Group ;
  ```

---

### 2.2 Quest 8: Categorical Syllogism Ingestion
In `quest8.png`, the document contains:
- Heading and 3 numbered premise statements.
- Interrogative conclusion query.
- Four candidate conclusions.

#### Segmented Document Blocks:
- **Block #1 [QUESTION PROMPT & PREMISES]:**
  ```text
  uestion Consider the following statements
  1. All programmers are logical
  2 _ Some logical people are crealive ,
  3 . No creative person is lazy
  Ihich of the following Conclusions is defintely true ?
  ```
- **Option A:** `Some programmers are Crealive`
- **Option B:** `No programmer is lazy`
- **Option C:** `Some logical people may be programmers _`
- **Option D:** `All Crealive People are Programmers _`

---

## 3. Option Reconstruction Rules & Heuristics

1. **Multiline Option Accumulation:** Once an option begins (via delimited `A.`, bracketed `[A]`, or bare `A SELECT...`), continuation lines that do not trigger a new option marker or question terminator accumulate into `current_opt["text"]`.
2. **Distinct Statement Delimitation:** A new SQL statement beginning with `SELECT` following a semicolon-terminated option automatically triggers a new option boundary.
3. **Sequential Missing Delimiter Inference:** If Option A and Option B have been captured, and an unlabelled statement block occurs immediately prior to Option D, the reconstructor assigns label `C`.
4. **Premise vs. Option Separation:** When lettered options `A`, `B`, `C`, `D` are present, numbered items prior to the question mark (`1.`, `2.`, `3.`) are treated as problem premises rather than candidate answer options.
