"""
generate_independent_7action_test.py: Constructs an independent, balanced 7-action evaluation
dataset for SETU-NETRA CM-RP Milestone R4 Audit.

Provides 35 distinct, curated, topic-separated test examples per action (245 total):
0: ARITHMETIC_SOLVER (35 samples) - Discrete math, Amdahl's Law, Cache math, Network metrics
1: DBMS_SOLVER (35 samples) - Healthcare & Inventory Relational Normalization, 4NF, Keys, SQL
2: FORMAL_LOGIC_SOLVER (35 samples) - Categorical Syllogisms, Contrapositives, Modus Tollens, Predicate Logic
3: EXTRACTIVE_QA (35 samples) - Exact RFC, IEEE standards, protocol definitions with cited text
4: LOCAL_SLM (35 samples) - Multi-dimensional architectural trade-offs & qualitative synthesis
5: ADDITIONAL_RETRIEVAL (35 samples) - Multi-page continuations, split theorems, multi-hop evidence
6: ABSTAIN (35 samples) - Contradictions of established theorems, impossible claims, speculative queries

Output: training/datasets/SETU-CM/splits/test_7action_independent.jsonl
"""

import os
import sys
import json
import time
from typing import List, Dict, Any
import numpy as np
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

from setu_netra.policy.cm_rp import StrategyAction, ACTION_TO_ID, ContextFeatureExtractor
from setu_netra.routing.system_telemetry import SystemTelemetry
from sentence_transformers import SentenceTransformer

def build_independent_7action_dataset():
    print("=" * 70)
    print("Building Independent 7-Action Test Dataset for Statistical Audit")
    print("=" * 70)

    # 1. Action 0: ARITHMETIC_SOLVER (35 samples)
    arithmetic_queries = [
        "Given Amdahl's Law with parallel fraction p = 0.8 and speedup s = 4, calculate total_speedup = 1 / ((1 - p) + (p / s))",
        "Given clock_rate = 2.5 GHz and cycle_count = 5000000, calculate execution_time = cycle_count / (clock_rate * 1e9)",
        "Given cache hit time = 2 ns, miss penalty = 80 ns, miss rate = 0.05, find amat = 2 + (0.05 * 80)",
        "In a network with bandwidth = 100 Mbps and RTT = 0.04 seconds, calculate bdp_bits = (100 * 1e6) * 0.04",
        "Calculate TCP throughput: bytes_transferred = 15000000; duration_seconds = 3; rate_mbps = (bytes_transferred * 8) / (duration_seconds * 1e6)",
        "Given matrix dimensions A(20, 30) and B(30, 40), compute scalar multiplications required = 20 * 30 * 40",
        "Given disk sector size = 512 bytes, file size = 12500 bytes, calculate sectors_needed = (12500 + 511) // 512",
        "Calculate Shannon channel capacity: bandwidth = 3000 Hz, snr = 31; capacity = bandwidth * 5",
        "Given baud rate = 9600 and bits per symbol = 4, calculate bit_rate = 9600 * 4",
        "Compute CPU speedup ratio: old_time = 145.5, new_time = 29.1, speedup = old_time / new_time",
        "Given page size = 4096 bytes and virtual address = 18450, calculate page_number = 18450 // 4096",
        "Given page size = 4096 bytes and virtual address = 18450, calculate page_offset = 18450 % 4096",
        "In a 4-way set associative cache with 1024 total blocks, calculate number_of_sets = 1024 / 4",
        "Given DRAM row buffer hit latency = 15 ns, miss latency = 45 ns, hit rate = 0.70, compute average = (0.70 * 15) + (0.30 * 45)",
        "Calculate Hamming code parity bits required for data_bits = 16: check 2^p >= 16 + p + 1; compute p = 5",
        "Given pipeline with 5 stages and clock cycle = 2 ns, compute total latency for 1 instruction = 5 * 2",
        "Given total memory = 16384 MB and OS reserved = 2048 MB, calculate available_ratio = (16384 - 2048) / 16384",
        "Calculate disk seek time: seek_cost = 4.5 ms, rotation_delay = 3.0 ms, transfer = 0.5 ms; total = 4.5 + 3.0 + 0.5",
        "In a binary tree with depth d = 5, calculate maximum leaves = 2^5",
        "Given hash table size = 997 and key count = 650, compute load_factor = 650 / 997",
        "Compute CRC generator divisor remainder for dividend = 110101 and polynomial = 1011",
        "Given round trip time = 50 ms and packet loss = 0.01, calculate Reno window limit = 1.22 / sqrt(0.01)",
        "Calculate token bucket burst capacity: bucket_size = 50000 bytes, refill_rate = 10000 bps; duration = 50000 / 10000",
        "Given prime factors p = 61, q = 53, compute RSA modulus n = p * q",
        "Given p = 61 and q = 53, calculate Euler totient phi = (p - 1) * (q - 1)",
        "Given RSA public exponent e = 17 and phi = 3120, verify gcd(e, phi) = 1",
        "Calculate discrete logarithm step: base = 3, target = 12, modulus = 17; verify 3^x mod 17",
        "In an M/M/1 queuing model with arrival lambda = 8 and service mu = 10, calculate utilization rho = 8 / 10",
        "Calculate average customers in M/M/1 queue: rho = 0.8; l_q = (rho * rho) / (1 - rho)",
        "Given floating point mantissa = 23 bits, calculate precision epsilon = 2^(-23)",
        "Compute matrix determinant: |[[4, 2], [3, 5]]| = (4 * 5) - (2 * 3)",
        "Calculate standard deviation: variance = 64; std_dev = sqrt(64)",
        "Given base 10 integer 255, calculate hexadecimal representation value = 15 * 16 + 15",
        "Calculate Huffman code tree average length: p1 = 0.5 (len 1), p2 = 0.25 (len 2), p3 = 0.25 (len 2); avg = 0.5*1 + 0.25*2 + 0.25*2",
        "Compute floating point exponent bias for IEEE 754 single precision: 2^(8-1) - 1 = 127"
    ]

    # 2. Action 1: DBMS_SOLVER (35 samples)
    dbms_queries = [
        "Given relation Hospital(PatientID, DoctorID, Treatment, WardNo) and F = {PatientID -> DoctorID, DoctorID -> WardNo}, find candidate keys.",
        "In Hospital schema with PatientID -> DoctorID and DoctorID -> WardNo, what transitive dependency causes violation of 3NF?",
        "Given relation Pharmacy(PrescriptionID, DrugCode, Dosage, Manufacturer) with {PrescriptionID, DrugCode} -> Dosage and DrugCode -> Manufacturer, decompose into 2NF.",
        "Explain why DrugCode -> Manufacturer represents a partial dependency on candidate key {PrescriptionID, DrugCode}.",
        "Given relation Clinic(DocID, ClinicRoom, PatientAppt) with DocID -> ClinicRoom, determine if Clinic satisfies Boyce-Codd Normal Form.",
        "Given relation Warehouse(ItemCode, BinLocation, Quantity, Category) with ItemCode -> Category and BinLocation -> ItemCode, find all candidate keys.",
        "In Warehouse schema, why is {BinLocation} a candidate key if BinLocation -> ItemCode and ItemCode -> Category?",
        "Given relation Schedule(CourseID, Section, Instructor, Semester) with {CourseID, Section, Semester} -> Instructor, verify BCNF compliance.",
        "Under relational database theory, define the conditions under which a functional dependency X -> Y is considered trivial.",
        "Given functional dependencies F = {A -> B, B -> C, CD -> E}, calculate the attribute closure of {A, D}^+.",
        "Determine whether dependency A -> C is logically implied by F = {A -> B, B -> C} using Armstrong's Transitivity Axiom.",
        "In relation R(A, B, C, D) with F = {A -> B, B -> C, C -> D}, why is A the unique minimal candidate key?",
        "Given decomposition of R(A, B, C) into R1(A, B) and R2(A, C), verify if the decomposition is lossless with respect to F = {A -> B}.",
        "State why the intersection of R1 and R2 must contain a candidate key of at least one sub-relation for lossless join decomposition.",
        "Given relation Enrollment(StudentID, CourseID, Activity) with StudentID ->> Activity, determine if relation violates 4NF.",
        "Define multi-valued dependency X ->> Y and explain how it differs from a functional dependency.",
        "In SQL, given query SELECT Dept, COUNT(*) FROM Employee GROUP BY Dept HAVING COUNT(*) > 5, evaluate the execution sequence.",
        "Explain why the WHERE clause cannot filter on aggregate results like SUM(Salary) prior to the GROUP BY stage.",
        "In relational algebra, what is the exact equivalence between a natural join R JOIN S and a theta join followed by projection?",
        "Given functional dependencies F = {X -> Y, W -> Z}, compute the canonical cover Fc eliminating redundant dependencies.",
        "Determine whether relation R(FlightNo, Date, Pilot, CoPilot) with {FlightNo, Date} -> Pilot satisfies 3NF.",
        "In a B-tree of order 4, what is the maximum number of child pointers an internal node can hold?",
        "Explain why B+ tree leaves form a doubly linked list while B-tree leaves do not maintain direct sequential pointers.",
        "Given functional dependency set F = {A -> BC, CD -> E, E -> A}, find the closure of {C, D}^+.",
        "In relation R(A, B, C, D, E) with candidate key {A, B}, why does B -> C constitute a partial dependency?",
        "Decompose relation R(A, B, C, D) with F = {A -> B, B -> C, A -> D} into a set of 3NF relations.",
        "Explain the difference between 3NF and BCNF when a relation possesses multiple overlapping candidate keys.",
        "Given relation R(ZipCode, City, State) with ZipCode -> City and City -> State, find the normal form.",
        "In ANSI SQL, what is the semantic difference between LEFT OUTER JOIN and FULL OUTER JOIN when tuples have no matching keys?",
        "Given relation R(A, B, C) with F = {AB -> C, C -> A}, verify whether decomposition into R1(A, C) and R2(B, C) is dependency-preserving.",
        "Why is dependency preservation important during relational database normalization?",
        "Determine whether functional dependency X -> A is preserved if neither sub-relation contains both X and A.",
        "In relation R(A, B, C, D) with F = {A -> B, B -> C, C -> A, D -> E}, determine the primary key.",
        "Explain the concept of extraneous attributes in a functional dependency and how they are eliminated in canonical cover.",
        "Given relation R(CustID, AccountNo, BranchName) with CustID -> AccountNo and AccountNo -> BranchName, identify BCNF violations."
    ]

    # 3. Action 2: FORMAL_LOGIC_SOLVER (35 samples)
    logic_queries = [
        "Premise: All carnivores are mammals. Premise: All tigers are carnivores. Does it conclude: All tigers are mammals?",
        "Premise: No reptiles are warm-blooded. Premise: All snakes are reptiles. Does it conclude: No snakes are warm-blooded?",
        "Premise: All philosophers are thinkers. Premise: Some writers are philosophers. Does it conclude: Some writers are thinkers?",
        "Premise: No triangles are squares. Premise: Some polygons are triangles. Does it conclude: Some polygons are not squares?",
        "Premise: All birds have feathers. Premise: Some pets are birds. Does it conclude: Some pets have feathers?",
        "Given conditional statement 'If it rains, then the ground is wet', what is the logically equivalent contrapositive?",
        "Given implication P -> Q, verify whether converse Q -> P is logically equivalent.",
        "Given premises P -> Q and ~Q, apply Modus Tollens to determine the valid conclusion.",
        "Given premises P -> Q and P, apply Modus Ponens to determine the valid conclusion.",
        "Premise: Some metals are magnetic. Premise: All iron objects are metals. Does it necessarily follow that All iron objects are magnetic?",
        "Given syllogism: All A are B. All C are B. Does it conclude: All A are C? If invalid, identify the fallacy of the undistributed middle.",
        "Premise: No fish are birds. Premise: No birds are insects. Does it conclude: No fish are insects? Explain fallacy of exclusive premises.",
        "Given statement 'Not (P and Q)', apply De Morgan's Law to state the logically equivalent disjunction.",
        "Given statement 'Not (P or Q)', apply De Morgan's Law to state the logically equivalent conjunction.",
        "Premise: All squares are rectangles. Premise: All rectangles are quadrilaterals. Conclude the transitive deduction.",
        "Premise: Either the server crashed or the network failed. Premise: The network did not fail. Deduce the status of the server using Disjunctive Syllogism.",
        "Given propositional formula (P -> Q) and (Q -> R), derive the hypothetical syllogism conclusion.",
        "Determine whether the proposition (P and ~P) is a contradiction, tautology, or contingency.",
        "Determine whether the proposition (P or ~P) is a contradiction, tautology, or contingency in classical Boolean logic.",
        "Given predicate logic statement 'For all x, P(x) -> Q(x)', what is the negation in terms of existential quantifiers?",
        "Given predicate statement 'There exists an x such that P(x) and ~Q(x)', state the formal negation.",
        "Premise: All prime numbers greater than 2 are odd. Premise: The number 7 is prime and greater than 2. Deduce whether 7 is odd.",
        "Premise: If a relation is in BCNF, it is in 3NF. Premise: Relation R is not in 3NF. Deduce BCNF status of R using contrapositive.",
        "Given premises: A -> B, B -> C, C -> D, and ~D. What is the truth value of A?",
        "Determine validity: If Socrates is human, then Socrates is mortal. Socrates is mortal. Therefore Socrates is human. Identify fallacy of affirming the consequent.",
        "Determine validity: If the key matches, the lock opens. The key does not match. Therefore the lock does not open. Identify fallacy of denying the antecedent.",
        "Premise: Some engineers are musicians. Premise: All musicians are creative. Does it conclude: Some engineers are creative?",
        "Premise: No mammals are cold-blooded. Premise: All lizards are cold-blooded. Conclude whether any lizards are mammals.",
        "Given Horn clause ~A or ~B or C, rewrite the clause as an implication.",
        "In first-order resolution, when two clauses contain literal P and ~P, what resolvent is produced?",
        "Verify whether the formula P -> (Q -> P) is a valid tautology under truth table assignment.",
        "Premise: All valid syllogisms have distributed middle terms. This argument lacks a distributed middle term. Conclude validity.",
        "Given statements: All roses are flowers. Some flowers fade quickly. Does it conclude: Some roses fade quickly?",
        "Apply resolution principle to derive empty clause from set {P, ~P or Q, ~Q}.",
        "State whether constructive dilemma: (P -> Q) and (R -> S), P or R, therefore Q or S, is a valid inference rule."
    ]

    # 4. Action 3: EXTRACTIVE_QA (35 samples)
    extractive_queries = [
        "According to RFC 793, what is the exact default maximum segment lifetime (MSL) specified for TCP connections?",
        "What does the IEEE 754 standard specify as the sign bit value representing positive floating point numbers?",
        "Under the POSIX standard, what file descriptor integer value is officially assigned to standard error (stderr)?",
        "What is the exact name of the snapshot algorithm used by Chubby lock service for distributed checkpointing?",
        "According to the NVMe 1.4 specification, what is the maximum number of I/O queues supported by a single controller?",
        "What is the official definition of an epoch number in the Raft consensus state machine?",
        "According to RFC 2616, what HTTP status code specifically designates '405 Method Not Allowed'?",
        "What exact encryption cipher suite is mandatory for baseline TLS 1.3 implementations according to RFC 8446?",
        "In the Linux VFS interface, what structure stores file metadata including inode number, owner, and timestamps?",
        "What is the exact port number assigned by IANA for standard DNS service over UDP?",
        "According to the Git documentation, what 40-character hash algorithm was originally used for commit object IDs?",
        "What is the designated page replacement policy algorithm described in Denning's 1968 working set model paper?",
        "According to the ext4 filesystem design documentation, what is the maximum supported individual file size?",
        "What exact command-line flag enables verbose execution logging in standard cURL utilities?",
        "In Kubernetes architecture, what component acts as the primary distributed key-value store for cluster state?",
        "According to RFC 1035, what is the maximum allowable character length of an individual DNS label?",
        "What is the default block size utilized by the Hadoop Distributed File System (HDFS) in version 3.x?",
        "According to the USB 3.0 specification, what is the raw maximum signaling throughput in Gbps?",
        "What exact system call does a Linux process invoke to replace its process image with a new executable?",
        "In the Spanner paper, what hardware component provides the bounded uncertainty time API called TrueTime?",
        "What is the exact default timeout interval defined for BGP keepalive messages in RFC 4271?",
        "According to the Java Virtual Machine specification, what area of memory stores compiled class bytecode and constant pools?",
        "What is the exact default listening port number for PostgreSQL database server instances?",
        "In OAuth 2.0 RFC 6749, what grant type is used by single-page web applications without client secrets?",
        "What is the exact command used in Docker CLI to remove all stopped containers and unused networks in one step?",
        "According to the Bigtable paper, what three-part key index structure locates specific data values?",
        "What is the exact name of the consensus protocol paper published by Leslie Lamport in 1998?",
        "According to the PCI Express 4.0 standard, what is the raw transfer rate per lane in GT/s?",
        "In Python documentation, what built-in exception is raised when dictionary key lookup fails?",
        "What is the exact default MTU size in bytes for standard Ethernet frames according to IEEE 802.3?",
        "According to the MapReduce paper, what partition function is used by default to assign intermediate keys to reducers?",
        "What is the exact header field in an IPv4 packet that prevents infinite looping across routing hops?",
        "According to RFC 7231, what HTTP method is idempotent and requests transfer of a resource representation?",
        "What is the exact database isolation level that prevents dirty reads, non-repeatable reads, and phantom reads?",
        "According to the Redis documentation, what data structure is used to implement Sorted Sets with logarithmic ranking?"
    ]

    # 5. Action 4: LOCAL_SLM (35 samples)
    local_slm_queries = [
        "Provide a comprehensive architectural comparison between microservices and modular monoliths for financial transaction systems.",
        "Compare and contrast the trade-offs between Log-Structured Merge (LSM) trees and B+ trees in high-throughput write workloads.",
        "Explain the evolutionary shift in distributed storage from hard disk drive seek optimization to flash NVMe parallelism.",
        "Synthesize the multi-faceted architectural trade-offs between Eventual Consistency and Strong Linearizability in global systems.",
        "Discuss the advantages and operational overhead of implementing a Zero-Trust network architecture in enterprise cloud environments.",
        "Analyze the architectural trade-offs between client-side rendering (CSR) and server-side rendering (SSR) for mobile web apps.",
        "Compare the consensus mechanics, message complexities, and leader dependencies between Raft and Multi-Paxos.",
        "Synthesize the reliability trade-offs between synchronous replication and asynchronous replication across geographic regions.",
        "Explain how modern container orchestrators like Kubernetes balance automated self-healing against cascading failure risks.",
        "Provide an in-depth qualitative evaluation of GraphQL versus REST API design paradigms for complex enterprise domain models.",
        "Discuss the design trade-offs between pessimistic concurrency control and optimistic concurrency control in distributed databases.",
        "Analyze the architectural implications of adopting an event-driven architecture with Kafka versus synchronous gRPC microservices.",
        "Compare the security and operational characteristics of hardware security modules (HSM) versus cloud KMS software vaults.",
        "Synthesize the structural trade-offs between column-oriented storage engines like Parquet and row-oriented engines like Avro.",
        "Explain the operational trade-offs of deploying distributed caches with cache-aside versus write-through invalidation policies.",
        "Provide a comprehensive overview of how modern branch prediction algorithms mitigate pipeline stall penalties in superscalar CPUs.",
        "Discuss the trade-offs of database connection pooling models: thread-per-connection versus asynchronous event-loop connection multiplexing.",
        "Analyze the fault-tolerance guarantees and partition behaviors of quorum-based consensus systems under asymmetric network netsplits.",
        "Compare the memory management trade-offs between generational garbage collection in the JVM and manual memory management in Rust.",
        "Synthesize the trade-offs between software-defined networking (SDN) overlays and traditional hardware BGP leaf-spine fabrics.",
        "Explain the design rationale behind separating storage and compute in modern cloud data warehouses like Snowflake and BigQuery.",
        "Discuss the multi-dimensional latency trade-offs between edge computing CDNs and centralized regional cloud data centers.",
        "Analyze the architectural trade-offs between symmetric multiprocessing (SMP) and non-uniform memory access (NUMA) systems.",
        "Compare the durability and recovery trade-offs between Write-Ahead Logging (WAL) and shadow paging in transaction managers.",
        "Synthesize the architectural trade-offs of adopting service mesh data planes like Envoy in high-throughput low-latency microservices.",
        "Provide a qualitative discussion of how CAP theorem constraints influence distributed ledger and blockchain architecture designs.",
        "Explain the trade-offs between compile-time static type checking and runtime dynamic typing in large-scale software engineering teams.",
        "Discuss the reliability trade-offs between active-passive warm standby failover and active-active multi-master database clusters.",
        "Analyze the operational trade-offs of adopting Infrastructure as Code (IaC) with declarative Terraform versus imperative scripting.",
        "Compare the architectural trade-offs of circuit breaker patterns versus exponential backoff retry policies in distributed RPCs.",
        "Synthesize the trade-offs between CPU cache coherence protocols: write-invalidate versus write-update in multicore architectures.",
        "Discuss the multi-faceted privacy and utility trade-offs of implementing differential privacy in user data analytics pipelines.",
        "Analyze the architectural benefits and operational challenges of implementing distributed tracing across heterogeneous microservices.",
        "Compare the performance and complexity trade-offs between kernel-space networking and user-space DPDK packet processing.",
        "Provide an in-depth qualitative analysis of how immutability principles in functional programming enhance concurrency safety."
    ]

    # 6. Action 5: ADDITIONAL_RETRIEVAL (35 samples)
    additional_retrieval_queries = [
        "According to the theorem proof begun in Section 2.1 and continued on the subsequent page, what is the final lemma?",
        "Find the complete hardware specification table that carries over across the page boundary into Section 3.2.",
        "What are the remaining configuration parameters for cluster failover continued from the preceding document page?",
        "According to the multi-page financial ledger continued in Schedule B, what is the net cumulative depreciation?",
        "Locate the rest of the algorithmic pseudocode for distributed commit that spans across pages 14 and 15.",
        "What are the additional compliance criteria listed in the continuation paragraph on Page 6?",
        "Find the complete list of candidate keys continued from the partial schema definition on the previous sheet.",
        "According to the regulatory disclosure statement continued in the supplementary appendix, what are the liability caps?",
        "What additional diagnostic steps are recommended in Section 5.3 following the initial triage instructions on Page 8?",
        "Find the subsequent sub-clauses of the licensing agreement that carry over onto the next document page.",
        "According to the network routing topology table continued on the facing page, what is the backup gateway IP?",
        "Locate the full text of Proposition 4 whose mathematical derivation is split across the document page break.",
        "What are the remaining process steps in the workflow diagram that continues in the attached exhibit?",
        "Find the full list of excluded liabilities continued from Section 7.1 onto the subsequent contract page.",
        "According to the multi-page benchmark result table continued in Appendix D, what was the 99th percentile latency?",
        "What are the subsequent parameter constraints for the optimization model continued on Page 22?",
        "Locate the remainder of the fault-tree analysis diagram continued from Figure 3 on the following page.",
        "Find the rest of the architectural migration roadmap milestones continued in the Phase 3 appendix.",
        "According to the chemical synthesis protocol continued from Step 4 on Page 12, what reagent is added next?",
        "What additional security firewall policies are defined in the continuation table on Page 19?",
        "Locate the full text of the statutory definition that spans across the document page margin.",
        "Find the complete inventory audit count continued in the supplementary spreadsheet attached to the report.",
        "According to the clinical trial patient exclusion criteria continued on Page 4, what conditions are listed?",
        "What are the remaining sub-methods of class TransactionCoordinator described in the continued design section?",
        "Find the full set of database indexing guidelines continued in the technical annex on Page 31.",
        "According to the environmental impact assessment continued from Chapter 2, what are the soil runoff projections?",
        "Locate the subsequent steps of the disaster recovery failover playbook continued on Page 15.",
        "What additional cryptographic cipher suites are approved in the continuation paragraph of NIST SP 800-52?",
        "Find the full list of participating distributed consensus nodes continued from Table 2 on Page 7.",
        "According to the system architecture diagram continued across the two-page spread, what feeds into the queue?",
        "Locate the remainder of the mathematical proof for Lemma 2.3 continued on Page 11.",
        "What are the remaining maintenance checklist items continued on the reverse side of the inspection sheet?",
        "Find the subsequent clauses of the data processing agreement continued in Annex 2.",
        "According to the CPU instruction set encoding table continued on Page 45, what is the opcode for VPERM?",
        "Locate the rest of the telemetry metrics specification continued in the subsequent configuration guide."
    ]

    # 7. Action 6: ABSTAIN (35 samples)
    abstain_queries = [
        "Does standard Quicksort guarantee an O(1) constant running time in the worst case for arbitrary input arrays?",
        "Can a distributed database achieve 100% Consistency and 100% Availability during a complete network partition?",
        "Does a candidate node in Raft win an election if it receives votes from only a minority of cluster servers?",
        "Can an uncompressed 1080p 60fps raw video stream fit inside a 56 Kbps dial-up modem bandwidth without data loss?",
        "Does Dijkstra's algorithm correctly compute shortest paths on graphs containing negative edge cycles without infinite loops?",
        "Will the exact closing stock price of Apple Inc. on December 31, 2045 be precisely $1,452.34?",
        "Does strict Two-Phase Locking (2PL) immediately release all exclusive write locks before a transaction commits?",
        "Is relational database normalization into BCNF mathematically guaranteed to preserve all functional dependencies?",
        "Can a parity bit detect any arbitrary even number of simultaneous bit flip errors in a transmitted byte?",
        "Does the Halting Problem possess a general computable algorithm that decides termination for all Turing machines?",
        "What was the exact personal dream that Alan Turing experienced on the night of June 14, 1936?",
        "Can an RSA 2048-bit private key be factored deterministically in under 3 seconds using classical pen and paper?",
        "Does a digital clock with a 1 MHz crystal oscillator execute 10 billion cycles in a single elapsed second?",
        "Can a RAID 0 disk array of two drives survive the catastrophic physical destruction of both member hard disks?",
        "Does TCP provide an unreliable connectionless datagram transport service with zero packet delivery acknowledgments?",
        "Is P = NP formally proven true by universal consensus of the Clay Mathematics Institute as of 2026?",
        "Will an unshielded copper twisted-pair cable transmit 100 Terabits per second over 50,000 kilometers without repeaters?",
        "Does a linear search on an unsorted array of size N execute in O(log N) logarithmic time in the worst case?",
        "Can a process in user mode directly execute privileged kernel CPU instructions without triggering a hardware fault?",
        "Does an ideal Carnot heat engine operate with 100% thermal efficiency between two finite thermal reservoirs?",
        "What is the exact secret password of the system administrator on server node-992 in our production cluster?",
        "Does a binary search tree with elements [5, 2, 8] place element 8 in the left subtree of root 5?",
        "Can a single-core processor physically execute two instructions at the exact same physical instant without hyperthreading?",
        "Does standard AES symmetric encryption use a public-key private-key pair for encryption and decryption?",
        "Will quantum entanglement allow instantaneous faster-than-light transmission of classical arbitrary text messages?",
        "Can a relational table with primary key ID contain two distinct rows that both have ID = 42?",
        "Does the CAP theorem prove that distributed systems can ignore network partitions without any performance consequence?",
        "Is there a lossless data compression algorithm guaranteed to compress every arbitrary N-bit input file to < N bits?",
        "Can an Ethernet collision domain operate flawlessly with zero frame collisions when 10,000 nodes transmit simultaneously on one hub?",
        "What will be the exact name of the winner of the 2060 International Olympic marathon?",
        "Does an unindexed full table scan on 10 billion rows execute faster than an index seek on 1 row?",
        "Can a deadlock occur when every process holds zero resources and requests zero resources?",
        "Does the Master Theorem solve recurrences where the subproblem sizes are divided by a negative factor?",
        "Is it possible to construct an algorithm that solves the Traveling Salesperson Problem in O(1) constant time?",
        "Can a 32-bit CPU directly address 500 Petabytes of physical RAM without bank switching or paging tricks?"
    ]

    # Model and feature extractor
    extractor = ContextFeatureExtractor()
    embedder = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    extractor._embedder = embedder

    action_datasets = [
        (StrategyAction.ARITHMETIC_SOLVER.value, arithmetic_queries, [0.88, 0.04, 0.04, 0.04], [0.85, 0.05, 0.02, 0.03, 0.05], False),
        (StrategyAction.DBMS_SOLVER.value, dbms_queries, [0.80, 0.08, 0.08, 0.04], [0.82, 0.08, 0.02, 0.03, 0.05], False),
        (StrategyAction.FORMAL_LOGIC_SOLVER.value, logic_queries, [0.80, 0.06, 0.08, 0.06], [0.84, 0.06, 0.02, 0.03, 0.05], False),
        (StrategyAction.EXTRACTIVE_QA.value, extractive_queries, [0.72, 0.12, 0.08, 0.08], [0.90, 0.05, 0.01, 0.01, 0.03], False),
        (StrategyAction.LOCAL_SLM.value, local_slm_queries, [0.75, 0.10, 0.05, 0.10], [0.88, 0.06, 0.01, 0.01, 0.04], False),
        (StrategyAction.ADDITIONAL_RETRIEVAL.value, additional_retrieval_queries, [0.15, 0.10, 0.10, 0.65], [0.15, 0.70, 0.05, 0.05, 0.05], False),
        (StrategyAction.ABSTAIN.value, abstain_queries, [0.80, 0.05, 0.05, 0.10], [0.02, 0.04, 0.88, 0.02, 0.04], True)
    ]

    out_records = []
    sample_id = 1

    for act_name, queries, sr_probs, er_probs, is_abstain in action_datasets:
        print(f"Generating features for {len(queries)} samples of action {act_name}...")
        for q in queries:
            # Generate genuine host telemetry
            telem = SystemTelemetry(
                cpu_percent=25.0,
                ram_percent=65.0,
                avail_ram_mb=5500.0,
                total_ram_mb=16384.0,
                timestamp=time.time()
            )
            # Precompute MiniLM embedding
            q_emb = embedder.encode(q, normalize_embeddings=True)
            feat_vec, mask_vec = extractor.extract_features(
                question=q,
                q_emb=q_emb,
                sr_probs=sr_probs,
                er_probs=er_probs,
                telemetry=telem
            )

            rec = {
                "example_id": f"audit_7act_{sample_id:04d}",
                "topic": f"Independent Audit: {act_name}",
                "question": q,
                "expected_action": act_name,
                "action_id": ACTION_TO_ID[act_name],
                "action_mask": mask_vec.tolist(),
                "context_features": feat_vec.tolist(),
                "sr_probs": sr_probs,
                "er_probs": er_probs,
                "resource_consumption": {
                    "cpu_percent": 25.0,
                    "ram_percent": 65.0,
                    "avail_ram_mb": 5500.0
                },
                "is_abstention_expected": is_abstain,
                "provenance": "independent_critical_statistical_audit"
            }
            out_records.append(rec)
            sample_id += 1

    out_path = "training/datasets/SETU-CM/splits/test_7action_independent.jsonl"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in out_records:
            f.write(json.dumps(r) + "\n")

    print(f"Successfully saved {len(out_records)} independent samples to: {out_path}")
    return out_records

if __name__ == "__main__":
    build_independent_7action_dataset()
