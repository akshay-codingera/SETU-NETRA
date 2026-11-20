"""
build_dataset.py: Dataset generator for SETU-ER (Evidence Relevance & Sufficiency).

Constructs a reproducible, non-leaking dataset across five epistemic classes:
1. SUFFICIENT (Passage(s) provide complete and sufficient premise to answer the question)
2. PARTIALLY_SUFFICIENT (Passage is semantically related, but critical necessary condition/premise is missing)
3. CONTRADICTORY (Passage directly asserts an opposite polarity, contradicting the query premise)
4. IRRELEVANT (Passage is from a completely unrelated domain, sharing no factual grounding)
5. UNVERIFIABLE (Question asks for subjective, speculative, or unanswerable claims given non-committal evidence)

Strictly partitions proposition topics across Train, Val, and Test to guarantee 0% question and topic leakage.
"""

import os
import json
import random
from typing import List, Dict, Any

# ==============================================================================
# 1. TOPIC-PARTITIONED PROPOSITION REPOSITORIES (ZERO LEAKAGE ACROSS SPLITS)
# ==============================================================================

# TRAIN PROPOSITIONS (12 distinct topics)
TRAIN_PROPOSITIONS = [
    # 1. Raft Leader Election
    {
        "domain": "DISTRIBUTED_SYSTEMS",
        "doc_id": "doc_raft_consensus",
        "topic": "Raft Leader Election",
        "q_sufficient": [
            "Under what condition does a candidate node win a leader election in Raft?",
            "What voting threshold is strictly required for a candidate to become leader in Raft?",
            "When does a Raft candidate successfully transition to the leader state?"
        ],
        "sufficient_passages": [
            "A candidate node wins a leader election if and only if it receives affirmative votes from a strict majority of servers in the cluster for that specific term.",
            "In Raft consensus, a candidate transitions to leader once it collects affirmative votes from more than half of the cluster nodes in the current term."
        ],
        "partial_passages": [
            "In the Raft consensus algorithm, leader election begins when an election timeout expires. A follower increments its term counter and votes for itself before sending RequestVote RPCs.",
            "Raft election safety ensures at most one leader per term. Servers vote on a first-come-first-served basis provided the candidate's log is at least as up-to-date as their own."
        ],
        "q_contradictory": [
            "Does a candidate node in Raft win an election with only a minority of server votes?",
            "Can a Raft node become leader if only 20% of cluster nodes vote in favor?"
        ],
        "contradictory_passages": [
            "In Raft consensus, a candidate node wins a leader election even if it receives only a minority of server votes, discarding majority requirements to accelerate failover.",
            "Raft permits a candidate to declare itself leader upon receiving a single vote from any peer, regardless of quorum majority."
        ],
        "q_unverifiable": [
            "Will Raft completely supersede Paxos across all distributed cloud infrastructure by 2035?",
            "Is Raft provably the final consensus protocol humankind will ever need?"
        ],
        "unverifiable_passages": [
            "Paxos and Raft are foundational consensus protocols widely taught in computer science. Future adoption across distributed hardware depends on ongoing industry developments.",
            "Comparative adoption of consensus protocols evolves alongside emerging hardware primitives, network topologies, and vendor ecosystems."
        ]
    },
    # 2. Raft Log Replication
    {
        "domain": "DISTRIBUTED_SYSTEMS",
        "doc_id": "doc_raft_consensus",
        "topic": "Raft Log Replication",
        "q_sufficient": [
            "How does a Raft leader ensure log consistency before committing an entry?",
            "When is an entry in a Raft leader's log officially considered committed?",
            "What replication condition commits an entry in Raft?"
        ],
        "sufficient_passages": [
            "A Raft leader commits an entry once it is replicated on a strict majority of follower nodes and has been written to persistent storage.",
            "An entry in Raft is considered committed after the leader receives successful AppendEntries acknowledgments from a majority of servers for an entry from its current term."
        ],
        "partial_passages": [
            "Raft log replication proceeds sequentially from the leader. The leader receives client command entries and serializes them into its local memory buffer.",
            "Followers append entries sent by the leader into their local logs and reply with success or failure based on the consistency check."
        ],
        "q_contradictory": [
            "Can a Raft leader commit an entry before writing it to a majority of servers?",
            "Does a Raft leader commit entries without verifying follower replication?"
        ],
        "contradictory_passages": [
            "A Raft leader commits client command entries immediately in volatile memory without waiting for follower acknowledgments or majority disk replication.",
            "In Raft, entries are committed instantly upon client receipt before any network transmission to follower nodes takes place."
        ],
        "q_unverifiable": [
            "Is Raft log replication the most energy-efficient consensus algorithm ever designed?",
            "Does Raft log replication consume less electrical power than all alternative protocols?"
        ],
        "unverifiable_passages": [
            "Energy efficiency in consensus protocols depends heavily on network switch topology, DRAM refresh rates, and CPU idle states, making general claims untestable.",
            "Measurement of power consumption across distributed state machines varies based on NIC hardware, kernel buffering, and storage media characteristics."
        ]
    },
    # 3. Translation Lookaside Buffer (TLB)
    {
        "domain": "OPERATING_SYSTEMS",
        "doc_id": "doc_operating_systems",
        "topic": "Translation Lookaside Buffer",
        "q_sufficient": [
            "What is the primary function of the Translation Lookaside Buffer (TLB) in virtual memory?",
            "Why do modern CPUs utilize an associative hardware TLB?",
            "How does a TLB accelerate memory address translation?"
        ],
        "sufficient_passages": [
            "The Translation Lookaside Buffer (TLB) is an associative hardware cache that stores recent virtual-to-physical page frame translations, avoiding costly multi-level page table walks.",
            "A TLB reduces memory translation latency by caching recently used virtual page number to physical frame number mappings directly in the processor MMU."
        ],
        "partial_passages": [
            "Virtual memory decouples the programmer's logical address space from physical RAM. The Memory Management Unit translates virtual addresses using multi-level page tables.",
            "Page tables are hierarchical data structures maintained by the kernel in physical memory that store the permissions and physical locations of memory pages."
        ],
        "q_contradictory": [
            "Does the TLB store disk blocks waiting to be written to secondary storage?",
            "Is the TLB a software queue for managing thread scheduling priorities?"
        ],
        "contradictory_passages": [
            "The Translation Lookaside Buffer (TLB) acts as a write-back disk sector buffer that stores modified file system blocks waiting to be flushed to non-volatile secondary storage.",
            "A TLB is a software data structure in the operating system kernel used to schedule high-priority real-time threads across CPU cores."
        ],
        "q_unverifiable": [
            "Will hardware TLBs be eliminated in 128-bit processor architectures?",
            "Will quantum memory addressing render all hardware translation buffers obsolete?"
        ],
        "unverifiable_passages": [
            "Future processor architectures exploring 128-bit virtual addressing may retain, modify, or replace associative TLBs depending on photonics and cryogenic memory designs.",
            "The evolution of future memory architectures beyond 64 bits involves speculative engineering proposals whose hardware adoption cannot be predicted with certainty."
        ]
    },
    # 4. Virtual Memory Thrashing
    {
        "domain": "OPERATING_SYSTEMS",
        "doc_id": "doc_operating_systems",
        "topic": "Virtual Memory Thrashing",
        "q_sufficient": [
            "What structural condition causes virtual memory thrashing in an operating system?",
            "Why does thrashing occur in a paged virtual memory system?",
            "What happens when the sum of process working sets exceeds physical RAM?"
        ],
        "sufficient_passages": [
            "Thrashing occurs when the aggregate working sets of all concurrent processes exceed physical RAM capacity, causing the system to spend more time swapping pages than executing instructions.",
            "Virtual memory thrashing is caused by severe memory overcommitment where processes continuously page-fault, saturating the I/O bus with swap operations."
        ],
        "partial_passages": [
            "Demand paging loads virtual memory pages into physical frames only upon an explicit page fault interrupt generated by the Memory Management Unit.",
            "The operating system maintains a free page frame list and uses replacement algorithms like LRU or CLOCK when allocating frames to active processes."
        ],
        "q_contradictory": [
            "Does thrashing increase CPU utilization and enhance application throughput?",
            "Does virtual memory thrashing prevent page fault interrupts entirely?"
        ],
        "contradictory_passages": [
            "Thrashing drastically increases CPU execution utilization and maximizes application computational throughput by prefetching memory pages at bus saturation speed.",
            "During thrashing, page faults drop to zero because all process pages are permanently locked in high-speed CPU registers."
        ],
        "q_unverifiable": [
            "Is Denning's working set model universally superior to all machine-learning page replacement policies?",
            "Will neural replacement policies permanently replace heuristic page replacement algorithms?"
        ],
        "unverifiable_passages": [
            "Comparative superiority between deterministic heuristics like Denning's Working Set Model and deep neural page replacement policies remains subjective and workload-dependent.",
            "Evaluating machine learning algorithms against heuristic page replacement policies involves varying trade-offs in inference overhead and cache locality."
        ]
    },
    # 5. Strict Two-Phase Locking (Strict 2PL)
    {
        "domain": "DBMS_CONCURRENCY",
        "doc_id": "doc_database_concurrency",
        "topic": "Strict Two-Phase Locking",
        "q_sufficient": [
            "How does Strict Two-Phase Locking (Strict 2PL) prevent cascading aborts?",
            "Why does Strict 2PL guarantee freedom from cascading rollbacks?",
            "What locking rule in Strict 2PL isolates uncommitted database modifications?"
        ],
        "sufficient_passages": [
            "Strict Two-Phase Locking (Strict 2PL) prevents cascading aborts by holding all exclusive write locks until the transaction explicitly commits or terminates, ensuring other transactions never read uncommitted data.",
            "Under Strict 2PL, exclusive locks are never released before transaction commit time, which prevents dirty reads and cascading rollbacks across concurrent transactions."
        ],
        "partial_passages": [
            "Two-Phase Locking (2PL) is a pessimistic concurrency control protocol divided into a growing phase where locks are acquired and a shrinking phase where locks are released.",
            "Concurrency control protocols guarantee ACID isolation properties by regulating the interleaved execution of transactions accessing shared data items."
        ],
        "q_contradictory": [
            "Does Strict 2PL release exclusive write locks prior to transaction commit?",
            "Can other transactions read dirty data under Strict Two-Phase Locking?"
        ],
        "contradictory_passages": [
            "Strict Two-Phase Locking (Strict 2PL) immediately releases exclusive write locks as soon as a write operation finishes, long before the transaction commits, intentionally exposing uncommitted dirty writes.",
            "In Strict 2PL, uncommitted data is freely exposed to all concurrent transactions because write locks are relinquished prior to logging the commit record."
        ],
        "q_unverifiable": [
            "Will all relational database engines abandon two-phase locking in favor of optimistic concurrency control?",
            "Is optimistic concurrency control objectively superior to pessimistic locking for all database workloads?"
        ],
        "unverifiable_passages": [
            "Whether pessimistic locking protocols will be fully replaced depends on hardware trends, non-volatile memory latency, and future distributed transaction workloads.",
            "Debates over pessimistic versus optimistic concurrency control depend on contention levels, read-write skew, and specific enterprise storage topologies."
        ]
    },
    # 6. ARIES Recovery Algorithm
    {
        "domain": "DBMS_CONCURRENCY",
        "doc_id": "doc_database_concurrency",
        "topic": "Write-Ahead Logging (WAL) & ARIES",
        "q_sufficient": [
            "What sequence of phases does the ARIES recovery algorithm execute following a crash?",
            "What are the three core operational phases in ARIES crash recovery?",
            "How does ARIES restore database consistency during restart recovery?"
        ],
        "sufficient_passages": [
            "The ARIES recovery algorithm operates in three sequential phases: the Analysis phase to identify dirty pages and active transactions, the Redo phase to repeat history, and the Undo phase to roll back uncommitted changes.",
            "During restart recovery, ARIES executes Analysis to determine dirty pages, followed by Redo to reconstruct state up to the crash, and finishes with Undo to reverse uncommitted transactions."
        ],
        "partial_passages": [
            "Write-Ahead Logging (WAL) guarantees database durability by ensuring all log records representing database page modifications are written to stable storage before data pages are flushed.",
            "Database recovery managers maintain log sequence numbers (LSNs) to track the progression of transactions across persistent storage."
        ],
        "q_contradictory": [
            "Does ARIES execute the Undo phase before performing the Redo phase during recovery?",
            "Does ARIES omit the Analysis phase and skip history reconstruction?"
        ],
        "contradictory_passages": [
            "The ARIES recovery algorithm executes the Undo phase first to discard changes, followed by Analysis, and completely skips the Redo phase to prevent replaying historical updates.",
            "Under ARIES, recovery begins by undoing all database pages immediately without reading log records, skipping the analysis of dirty page tables entirely."
        ],
        "q_unverifiable": [
            "Is ARIES the cleanest recovery algorithm ever formulated in computer science?",
            "Will ARIES remain the recovery gold standard forever?"
        ],
        "unverifiable_passages": [
            "Aesthetic qualities such as elegance or cleanliness of recovery algorithms are subjective architectural opinions rather than scientifically verifiable empirical facts.",
            "Long-term persistence of recovery paradigms depends on future developments in byte-addressable non-volatile memory and distributed architectures."
        ]
    },
    # 7. Second Normal Form (2NF)
    {
        "domain": "FORMAL_LOGIC_DBMS",
        "doc_id": "doc_normalization_logic",
        "topic": "Second Normal Form (2NF)",
        "q_sufficient": [
            "When does a relation in First Normal Form satisfy Second Normal Form (2NF)?",
            "What condition regarding functional dependencies defines Second Normal Form?",
            "How is Second Normal Form characterized in relational database theory?"
        ],
        "sufficient_passages": [
            "A relation in 1NF satisfies Second Normal Form (2NF) if and only if no non-prime attribute is functionally dependent on any proper subset of any candidate key (it is free from partial functional dependencies).",
            "In relational database theory, 2NF requires that every non-key attribute is fully functionally dependent on the primary key, eliminating partial dependencies on composite keys."
        ],
        "partial_passages": [
            "Relational normalization decomposes schemas to eliminate data redundancy and update anomalies. A candidate key uniquely determines every attribute in a relation.",
            "First Normal Form requires that all column values are atomic and that the relation contains no repeating groups or nested relations."
        ],
        "q_contradictory": [
            "Does 2NF allow non-prime attributes to be partially dependent on a composite candidate key?",
            "Does Second Normal Form mandate that non-prime attributes depend only on a fraction of a candidate key?"
        ],
        "contradictory_passages": [
            "Second Normal Form (2NF) explicitly permits non-prime attributes to be partially dependent on proper subsets of composite candidate keys, encouraging partial key redundancy.",
            "Under 2NF, relations are required to store non-prime attributes that depend on only one part of a composite primary key, preserving partial dependencies."
        ],
        "q_unverifiable": [
            "Will Boyce-Codd Normal Form remain the gold standard of relational design indefinitely?",
            "Is higher normal form decomposition always preferable to denormalized storage in practice?"
        ],
        "unverifiable_passages": [
            "The indefinite status of BCNF as a design gold standard cannot be evaluated empirically, as schema paradigms evolve with vector, graph, and document database trends.",
            "Trade-offs between strict mathematical normalization and query performance through denormalization depend on application-specific latency requirements."
        ]
    },
    # 8. Propositional Logic Contrapositive
    {
        "domain": "FORMAL_LOGIC_DBMS",
        "doc_id": "doc_normalization_logic",
        "topic": "Syllogistic Validity",
        "q_sufficient": [
            "Under classical propositional semantics, what is the contrapositive of (P -> Q)?",
            "What formula represents the logically equivalent contrapositive of implication P -> Q?",
            "How is the contrapositive of a conditional proposition constructed?"
        ],
        "sufficient_passages": [
            "In classical propositional logic, the contrapositive of the conditional assertion (P -> Q) is (~Q -> ~P), which is strictly semantically equivalent to (P -> Q).",
            "The contrapositive of an implication P implies Q is not-Q implies not-P, having an identical truth table across all boolean interpretations."
        ],
        "partial_passages": [
            "In formal logic, conditional statements establish implication relationships between antecedent P and consequent Q, evaluated across truth table assignments.",
            "Logical equivalence between propositional statements means that both statements evaluate to the same truth value under all model assignments."
        ],
        "q_contradictory": [
            "Is the contrapositive of (P -> Q) logically equivalent to (P -> ~Q)?",
            "Is the contrapositive of an implication formed by keeping the consequent unchanged?"
        ],
        "contradictory_passages": [
            "In classical propositional logic, the contrapositive of (P -> Q) is defined as (P -> ~Q), which reverses the truth value and inverts the antecedent's truth polarity.",
            "The contrapositive of implication P -> Q is constructed as Q -> P, which is the converse and is not logically equivalent."
        ],
        "q_unverifiable": [
            "Is classical propositional logic philosophically superior to intuitionistic logic?",
            "Is the Law of Excluded Middle the most profound truth in human contemplation?"
        ],
        "unverifiable_passages": [
            "Philosophical preference between classical semantics (admitting the Law of Excluded Middle) and intuitionistic constructive logic is an epistemological stance, not an empirical fact.",
            "Mathematical logicians differ on whether constructive proofs without excluded middle offer deeper computational insight than classical proofs."
        ]
    },
    # 9. 2D Convolution Complexity
    {
        "domain": "ALGORITHMS_COMPLEXITY",
        "doc_id": "doc_algorithms_complexity",
        "topic": "2D Convolution Computational Complexity",
        "q_sufficient": [
            "What is the computational complexity of performing direct 2D spatial convolution of an H x W image with a K x K kernel?",
            "How many arithmetic operations are required for direct 2D convolution of an H x W image by a K x K filter?",
            "What is the big-O complexity of direct spatial 2D filtering?"
        ],
        "sufficient_passages": [
            "The computational complexity of direct 2D spatial convolution on an image of dimensions H x W with a kernel of size K x K (stride 1, direct domain) is O(H * W * K^2) arithmetic operations.",
            "Direct 2D convolution requires performing K^2 multiply-accumulate operations for each of the H * W pixel locations, resulting in asymptotic complexity O(H * W * K^2)."
        ],
        "partial_passages": [
            "Convolution applies a discrete spatial sliding filter across an input matrix, computing elementwise inner products between kernel weights and local receptive field pixels.",
            "In digital image processing, 2D spatial filtering is frequently accelerated using Fast Fourier Transforms (FFT) or Winograd minimal filtering algorithms."
        ],
        "q_contradictory": [
            "Does direct 2D spatial convolution of an H x W image with a K x K kernel run in O(1) constant time?",
            "Is direct 2D image convolution independent of image dimensions and kernel size?"
        ],
        "contradictory_passages": [
            "Direct 2D spatial convolution on an H x W image with a K x K kernel executes in O(1) constant time regardless of image dimensions, kernel size, or stride parameter.",
            "The time complexity of direct spatial convolution is O(log K), requiring no multiplicative operations proportional to image height or width."
        ],
        "q_unverifiable": [
            "Will quantum computers reduce all convolution operations to O(1) time within ten years?",
            "Is frequency-domain convolution the most elegant algorithm in computer science?"
        ],
        "unverifiable_passages": [
            "Future timelines regarding quantum algorithmic breakthroughs and polynomial speedups for spatial filtering over the next decade are speculative and unverified.",
            "Aesthetic claims regarding the mathematical elegance of frequency-domain versus direct-domain filtering reflect human preference."
        ]
    },
    # 10. Quicksort Worst-Case Complexity
    {
        "domain": "ALGORITHMS_COMPLEXITY",
        "doc_id": "doc_algorithms_complexity",
        "topic": "Quicksort Worst-Case Complexity",
        "q_sufficient": [
            "What is the worst-case asymptotic time complexity of standard Quicksort, and when does it occur?",
            "Under what partitioning condition does Quicksort exhibit O(N^2) worst-case time complexity?",
            "Why can standard Quicksort degrade to quadratic running time?"
        ],
        "sufficient_passages": [
            "The worst-case asymptotic time complexity of Quicksort is O(N^2), occurring when the chosen pivot consistently partitions the array into highly unbalanced subproblems of sizes 0 and N-1.",
            "Standard Quicksort exhibits O(N^2) time complexity when input data is already sorted and the implementation picks the first or last element as the pivot."
        ],
        "partial_passages": [
            "Quicksort is a divide-and-conquer sorting algorithm that selects a pivot element and partitions the array such that elements smaller than the pivot precede larger elements.",
            "On average, Quicksort performs O(N log N) comparisons when partitions are reasonably balanced, making it one of the most widely used general-purpose sorts."
        ],
        "q_contradictory": [
            "Is the worst-case time complexity of standard Quicksort strictly O(log N)?",
            "Does Quicksort guarantee O(N) linear execution time in the worst case?"
        ],
        "contradictory_passages": [
            "The worst-case asymptotic time complexity of standard Quicksort is strictly O(log N), guaranteeing logarithmic execution time even on reverse-sorted inputs.",
            "In the worst case, Quicksort runs in linear O(N) time because unbalanced partitions reduce the number of comparison passes to zero."
        ],
        "q_unverifiable": [
            "Is Quicksort the most aesthetically pleasing sorting algorithm in human history?",
            "Will randomized Quicksort remain the primary in-memory sort algorithm indefinitely?"
        ],
        "unverifiable_passages": [
            "Subjective claims regarding the aesthetic beauty or artistic elegance of divide-and-conquer sorting implementations cannot be settled through mathematical proof.",
            "The longevity of sorting algorithms in standard libraries depends on future hardware cache topologies and vectorized SIMD instruction sets."
        ]
    },
    # 11. TCP Congestion Control (AIMD)
    {
        "domain": "COMPUTER_NETWORKING",
        "doc_id": "doc_tcp_congestion",
        "topic": "TCP Congestion Control AIMD",
        "q_sufficient": [
            "How does TCP Additive Increase Multiplicative Decrease (AIMD) adjust the congestion window?",
            "What are the mathematical rules governing congestion window adjustments in TCP AIMD?",
            "How does TCP AIMD achieve stability and fairness during network congestion?"
        ],
        "sufficient_passages": [
            "Under TCP AIMD, the congestion window increases linearly by one Maximum Segment Size (MSS) per round-trip time without loss, and halves multiplicatively upon detecting packet loss.",
            "TCP AIMD adjusts the congestion window by adding 1 MSS per RTT during congestion avoidance and multiplying the window by 0.5 upon packet drop detection."
        ],
        "partial_passages": [
            "TCP congestion control prevents network collapse by dynamically adjusting transmission rates based on implicit packet loss feedback.",
            "The slow start phase in TCP exponentially increments the congestion window until reaching the slow start threshold."
        ],
        "q_contradictory": [
            "Does TCP AIMD double the congestion window upon packet loss detection?",
            "Does AIMD increase the congestion window multiplicatively and decrease it additively?"
        ],
        "contradictory_passages": [
            "TCP AIMD doubles the congestion window multiplicatively upon detecting packet loss and decreases the window by a fixed subtraction of one byte during normal acknowledgment.",
            "Under AIMD, packet drops trigger an immediate exponential doubling of the sender's transmission rate to force packets through congested routers."
        ],
        "q_unverifiable": [
            "Is TCP BBR undeniably superior to all AIMD-based TCP congestion algorithms in every network scenario?",
            "Will loss-based congestion control algorithms disappear from the internet entirely by 2030?"
        ],
        "unverifiable_passages": [
            "Evaluating whether model-based algorithms like BBR outperform loss-based AIMD variants depends on bufferbloat, cellular jitter, and competing cross-traffic.",
            "Future adoption curves for transport protocols across global internet routers depend on middlebox support and kernel deployment schedules."
        ]
    },
    # 12. Copy-on-Write (COW) Fork
    {
        "domain": "OPERATING_SYSTEMS",
        "doc_id": "doc_operating_systems",
        "topic": "Copy-on-Write Memory Management",
        "q_sufficient": [
            "How does Copy-on-Write (COW) optimize process creation during a fork system call?",
            "Why does the fork system call avoid duplicating physical memory pages immediately?",
            "How does Copy-on-Write reduce the overhead of the fork system call?"
        ],
        "sufficient_passages": [
            "Copy-on-Write (COW) allows parent and child processes to share identical physical pages marked read-only upon fork, duplicating a page only when either process attempts a write operation.",
            "Under Copy-on-Write, the fork system call simply copies page table entries rather than physical frames; actual page duplication is deferred until a write fault occurs."
        ],
        "partial_passages": [
            "In Unix-like systems, the fork system call creates a new child process that is an exact duplicate of the calling parent process with its own PID.",
            "Process address spaces contain text, data, heap, and stack segments managed through architectural virtual memory translation tables."
        ],
        "q_contradictory": [
            "Does Copy-on-Write duplicate all physical memory pages into fresh physical frames immediately upon fork?",
            "Does Copy-on-Write prevent child processes from ever modifying shared memory data?"
        ],
        "contradictory_passages": [
            "Copy-on-Write (COW) eagerly allocates and duplicates every physical memory frame into brand new physical addresses immediately during the fork call, prohibiting page sharing.",
            "Under Copy-on-Write, if a child process writes to a page, the write is permanently rejected by the OS and the child process is terminated."
        ],
        "q_unverifiable": [
            "Is the Unix fork/exec model the most elegant process abstraction ever conceived?",
            "Will all modern operating systems replace the fork system call with spawn-only semantics?"
        ],
        "unverifiable_passages": [
            "Software engineering debates over the elegance of fork versus direct spawn primitives involve contrasting trade-offs in thread safety and address space duplication.",
            "Whether general-purpose kernels will deprecate fork in favor of posix_spawn remains subject to legacy compatibility constraints."
        ]
    }
]

# VAL PROPOSITIONS (4 distinct held-out topics, 0% overlap with Train or Test)
VAL_PROPOSITIONS = [
    # 13. CAP Theorem
    {
        "domain": "DISTRIBUTED_SYSTEMS",
        "doc_id": "doc_cap_theorem",
        "topic": "CAP Theorem Partition Tradeoff",
        "q_sufficient": [
            "According to the CAP theorem, what trade-off must a distributed system make during a network partition?",
            "Why cannot a distributed data store guarantee both Consistency and Availability during a partition?",
            "What does Eric Brewer's CAP theorem state regarding network partitions?"
        ],
        "sufficient_passages": [
            "According to the CAP theorem, when a network partition (P) occurs, a distributed system must choose between Consistency (C), returning an error or stalling, and Availability (A), returning stale data.",
            "Under the CAP theorem, in the presence of network partitions, a distributed system can guarantee either strong consistency or high availability, but not both simultaneously."
        ],
        "partial_passages": [
            "The CAP theorem categorizes distributed systems into CA, CP, and AP models based on their operational guarantees.",
            "Network partitions are inevitable communication failures in distributed systems where nodes become divided into unreachable sub-clusters."
        ],
        "q_contradictory": [
            "Does the CAP theorem prove that distributed systems can guarantee 100% Consistency, 100% Availability, and Partition Tolerance simultaneously?",
            "Does the CAP theorem state that network partitions never force trade-offs between consistency and availability?"
        ],
        "contradictory_passages": [
            "The CAP theorem mathematically proves that any distributed system can simultaneously guarantee perfect Consistency, complete Availability, and robust Partition Tolerance under all failure modes.",
            "Under Brewer's theorem, distributed databases are immune to network partitions and never need to sacrifice consistency or availability."
        ],
        "q_unverifiable": [
            "Will quantum entanglement communication render the CAP theorem completely obsolete by eliminating network partitions?",
            "Is the CAP theorem the most profound law in computer science?"
        ],
        "unverifiable_passages": [
            "Whether quantum communication channels can prevent packet delays or distributed partition states remains open to physical and engineering validation.",
            "Assessing the philosophical profundity of the CAP theorem compared to other computational theorems is a matter of personal opinion."
        ]
    },
    # 14. Deadlock Banker's Algorithm
    {
        "domain": "OPERATING_SYSTEMS",
        "doc_id": "doc_bankers_algorithm",
        "topic": "Banker's Algorithm Safe State",
        "q_sufficient": [
            "Under what condition does Dijkstra's Banker's Algorithm grant a resource request?",
            "How does the Banker's Algorithm determine if resource allocation will leave the system in a safe state?",
            "What criterion in the Banker's Algorithm prevents deadlock?"
        ],
        "sufficient_passages": [
            "The Banker's Algorithm grants a resource request if and only if the resulting resource allocation leaves the system in a safe state, meaning there exists a safe execution sequence where all processes can terminate.",
            "Dijkstra's Banker's Algorithm evaluates whether granting requested resources permits at least one sequential ordering of remaining processes to satisfy their maximum resource claims."
        ],
        "partial_passages": [
            "Deadlock avoidance requires the operating system to have a priori knowledge of the maximum resources each process will declare during execution.",
            "A system is in a deadlock state when every process in a set is waiting for an event that can only be caused by another process in the set."
        ],
        "q_contradictory": [
            "Does the Banker's Algorithm grant resource requests that transition the system into an unsafe state?",
            "Does the Banker's Algorithm allocate resources immediately without checking for safe execution sequences?"
        ],
        "contradictory_passages": [
            "The Banker's Algorithm deliberately grants resource requests that drive the system directly into an unsafe state, prioritizing instant allocation over deadlock prevention.",
            "Under Dijkstra's Banker's Algorithm, resource requests are granted greedily without testing whether a safe execution order exists."
        ],
        "q_unverifiable": [
            "Will all modern operating system kernels integrate the Banker's Algorithm within the next decade?",
            "Is the Banker's Algorithm the most mathematically elegant deadlock strategy ever conceived?"
        ],
        "unverifiable_passages": [
            "Most operating system kernels avoid the Banker's Algorithm because processes rarely declare maximum resource claims in advance.",
            "Subjective appraisals regarding algorithmic elegance cannot be verified empirically."
        ]
    },
    # 15. Multi-Version Concurrency Control (MVCC)
    {
        "domain": "DBMS_CONCURRENCY",
        "doc_id": "doc_mvcc_concurrency",
        "topic": "Multi-Version Concurrency Control (MVCC)",
        "q_sufficient": [
            "How does Multi-Version Concurrency Control (MVCC) prevent read transactions from blocking write transactions?",
            "Why do readers not block writers and writers not block readers under MVCC?",
            "How does MVCC achieve non-blocking read isolation in relational databases?"
        ],
        "sufficient_passages": [
            "MVCC allows readers and writers to execute concurrently without blocking by maintaining multiple timestamped versions of data items, allowing read transactions to view a consistent snapshot.",
            "Under MVCC, write operations create new versions of rows rather than overwriting existing records in place, enabling concurrent readers to inspect previous valid versions without locking."
        ],
        "partial_passages": [
            "Relational database engines such as PostgreSQL and InnoDB utilize MVCC to deliver snapshot isolation and high concurrency for analytical workloads.",
            "Vacuuming or undo space reclamation is necessary in MVCC engines to purge dead tuple versions no longer visible to active transactions."
        ],
        "q_contradictory": [
            "Does MVCC require read operations to acquire exclusive write locks that block all concurrent writers?",
            "Does MVCC overwrite existing data in place and force read transactions to wait for write locks?"
        ],
        "contradictory_passages": [
            "MVCC enforces strict exclusive locking on every read operation, mandating that readers completely block all concurrent write transactions until query termination.",
            "Under MVCC, every read operation overwrites previous row records immediately and halts all concurrent database transactions."
        ],
        "q_unverifiable": [
            "Is MVCC the ultimate concurrency model that will replace all locking protocols permanently?",
            "Will any concurrency control paradigm ever surpass snapshot isolation in popularity?"
        ],
        "unverifiable_passages": [
            "Whether MVCC remains the dominant concurrency control model depends on future memory technologies like fast persistent memory (NVDIMMs).",
            "Predictions regarding long-term dominance across database architectures reflect speculation rather than determinable facts."
        ]
    },
    # 16. Dijkstra's Algorithm with Min-Heap
    {
        "domain": "ALGORITHMS_COMPLEXITY",
        "doc_id": "doc_dijkstra_heap",
        "topic": "Dijkstra Algorithm with Min-Heap Complexity",
        "q_sufficient": [
            "What is the asymptotic time complexity of Dijkstra's algorithm implemented with a binary min-heap?",
            "How many operations does Dijkstra's algorithm take on a graph with V vertices and E edges using a binary heap?",
            "What is the running time of Dijkstra's shortest path algorithm using a min-priority queue?"
        ],
        "sufficient_passages": [
            "The asymptotic time complexity of Dijkstra's algorithm implemented with a binary min-heap is O((V + E) log V), where V is the number of vertices and E is the number of edges.",
            "Using a binary min-heap, Dijkstra's algorithm requires O(V log V) extract-min operations and O(E log V) decrease-key operations, yielding total running time O((V + E) log V)."
        ],
        "partial_passages": [
            "Dijkstra's algorithm computes the shortest path from a single source vertex to all other vertices in a directed or undirected graph with non-negative edge weights.",
            "The algorithm iteratively relaxes edges incident to the closest unvisited vertex until all reachable vertices have been processed."
        ],
        "q_contradictory": [
            "Does Dijkstra's algorithm with a binary min-heap have a time complexity of O(1)?",
            "Can Dijkstra's algorithm correctly compute shortest paths on graphs with negative edge weights?"
        ],
        "contradictory_passages": [
            "Dijkstra's algorithm implemented with a binary min-heap executes in O(1) constant time regardless of graph size or edge count.",
            "Dijkstra's algorithm is guaranteed to produce correct shortest path distances on arbitrary graphs containing negative edge weights and negative cycles."
        ],
        "q_unverifiable": [
            "Is Dijkstra's algorithm the most brilliant graph algorithm ever conceived in mathematics?",
            "Will quantum graph algorithms replace Dijkstra's algorithm in every routing application?"
        ],
        "unverifiable_passages": [
            "Evaluating whether Dijkstra's algorithm is the most brilliant algorithm involves personal subjective aesthetic appraisal.",
            "Quantum shortest path algorithms face hardware scaling limitations whose future deployment timeline cannot be verified."
        ]
    }
]

# TEST PROPOSITIONS (4 distinct held-out topics, 0% overlap with Train or Val)
TEST_PROPOSITIONS = [
    # 17. Two-Phase Commit (2PC)
    {
        "domain": "DISTRIBUTED_SYSTEMS",
        "doc_id": "doc_two_phase_commit",
        "topic": "Two-Phase Commit Protocol",
        "q_sufficient": [
            "What is the primary vulnerability of the standard Two-Phase Commit (2PC) protocol when the coordinator crashes?",
            "Why is Two-Phase Commit known as a blocking atomic commitment protocol?",
            "What happens to participants in 2PC if the coordinator fails during the commit phase?"
        ],
        "sufficient_passages": [
            "The primary vulnerability of Two-Phase Commit (2PC) is that it is a blocking protocol: if the coordinator crashes after participants vote to commit, participants remain blocked holding locks indefinitely until the coordinator recovers.",
            "Under 2PC, participant nodes in the prepared state must wait indefinitely if the coordinator crashes before broadcasting the commit or abort decision, blocking shared resources."
        ],
        "partial_passages": [
            "Two-Phase Commit is an atomic commitment protocol consisting of a prepare phase where participants vote and a commit phase where the coordinator announces the global outcome.",
            "Atomic commitment protocols ensure that all distributed database participants either commit or abort a distributed transaction uniformly."
        ],
        "q_contradictory": [
            "Is standard Two-Phase Commit a non-blocking protocol that guarantees immediate decision resolution even if the coordinator crashes?",
            "Does 2PC allow participant nodes to independently abort without blocking when a coordinator fails in the prepared state?"
        ],
        "contradictory_passages": [
            "Standard Two-Phase Commit (2PC) is a completely non-blocking protocol: if the coordinator crashes, participants instantly resolve the transaction in under one millisecond with zero blocking.",
            "Under 2PC, participant nodes never block and can unilaterally abort even after sending affirmative commit votes to the coordinator."
        ],
        "q_unverifiable": [
            "Will all modern distributed databases abandon Two-Phase Commit completely in favor of Three-Phase Commit?",
            "Is Three-Phase Commit the cleanest consensus protocol ever created?"
        ],
        "unverifiable_passages": [
            "Adoption of Three-Phase Commit is limited by complexity and vulnerability to network partitions, leaving future migration trends unresolved.",
            "Subjective aesthetic criteria regarding consensus protocols are matters of engineering style rather than provable facts."
        ]
    },
    # 18. B+ Tree Node Splitting
    {
        "domain": "DBMS_STORAGE",
        "doc_id": "doc_bplus_tree",
        "topic": "B+ Tree Node Splitting Mechanism",
        "q_sufficient": [
            "What occurs when an insertion causes a B+ tree leaf node to exceed its maximum capacity?",
            "How does a B+ tree handle leaf node overflow during a record insertion?",
            "What structural rebalancing occurs when a B+ tree leaf splits?"
        ],
        "sufficient_passages": [
            "When a B+ tree leaf node exceeds its maximum capacity, it splits into two leaf nodes each containing half the keys, and the lowest key of the new right node is copied up to the parent internal node.",
            "During a B+ tree leaf overflow, the node divides into two balanced leaf nodes with roughly ceiling(M/2) keys, and the split key is duplicated into the parent node to guide future searches."
        ],
        "partial_passages": [
            "B+ trees are self-balancing search trees widely used in database indices and file systems to provide logarithmic search, insert, and delete operations.",
            "In a B+ tree, all leaf nodes are connected via a doubly-linked list at the bottom level to enable efficient range scans."
        ],
        "q_contradictory": [
            "Does a B+ tree delete half of its existing keys when a leaf node overflows during insertion?",
            "Does an overflowing B+ tree leaf node increase tree height by O(N) linear levels immediately?"
        ],
        "contradictory_passages": [
            "When a B+ tree leaf node exceeds capacity, it permanently deletes half of its stored keys to make room rather than allocating a new node.",
            "Leaf node overflow in a B+ tree causes the tree height to increase by N levels immediately, destroying logarithmic balance."
        ],
        "q_unverifiable": [
            "Will learned index structures (neural models) completely replace B+ trees in all relational databases by 2032?",
            "Are B+ trees the most perfect data structure ever invented by humanity?"
        ],
        "unverifiable_passages": [
            "Whether neural learned indices will replace B+ trees remains contested due to dynamic write amplification and retraining overhead.",
            "Claiming that a specific data structure is 'the most perfect' is an aesthetic valuation outside the scope of factual verification."
        ]
    },
    # 19. Master Theorem Divide-and-Conquer
    {
        "domain": "ALGORITHMS_COMPLEXITY",
        "doc_id": "doc_master_theorem",
        "topic": "Master Theorem Divide-and-Conquer Recurrence",
        "q_sufficient": [
            "Under the Master Theorem, what is the asymptotic solution to the recurrence T(n) = 2T(n/2) + O(n)?",
            "What time complexity does the Master Theorem give for standard Merge Sort recurrence T(n) = 2T(n/2) + Theta(n)?",
            "According to Case 2 of the Master Theorem, what is the complexity of T(n) = 2T(n/2) + n?"
        ],
        "sufficient_passages": [
            "According to Case 2 of the Master Theorem, the recurrence T(n) = 2T(n/2) + O(n) resolves to Theta(n log n) because f(n) = Theta(n^(log_b a)) where a=2, b=2, so log_b a = 1.",
            "Under the Master Theorem Case 2, when the work at each divide step f(n) matches n^(log_b a), the total asymptotic complexity evaluates to Theta(n log n)."
        ],
        "partial_passages": [
            "The Master Theorem provides a cookbook solution in asymptotic terms for divide-and-conquer recurrences of the form T(n) = aT(n/b) + f(n).",
            "Divide-and-conquer algorithms partition a problem into a subproblems of size n/b, solve each subproblem recursively, and combine the solutions."
        ],
        "q_contradictory": [
            "Does the Master Theorem evaluate T(n) = 2T(n/2) + O(n) to exponential time O(2^n)?",
            "Under the Master Theorem, does T(n) = 2T(n/2) + Theta(n) evaluate to O(1) constant time?"
        ],
        "contradictory_passages": [
            "According to the Master Theorem, the recurrence T(n) = 2T(n/2) + O(n) evaluates to exponential time O(2^n), growing exponentially with input size.",
            "The Master Theorem proves that the recurrence T(n) = 2T(n/2) + Theta(n) operates in O(1) constant time regardless of n."
        ],
        "q_unverifiable": [
            "Is the Master Theorem the single greatest mathematical formula ever published in computer science education?",
            "Will automated theorem provers replace human understanding of recurrences completely?"
        ],
        "unverifiable_passages": [
            "Ranking mathematical theorems by their pedagogical greatness is a subjective appraisal varying widely among educators.",
            "The degree to which automated reasoning will replace foundational human analysis of algorithms remains subject to ongoing debate."
        ]
    },
    # 20. DNS Recursive Resolution
    {
        "domain": "COMPUTER_NETWORKING",
        "doc_id": "doc_dns_resolution",
        "topic": "DNS Recursive Resolution Protocol",
        "q_sufficient": [
            "What sequence of servers does a DNS recursive resolver query when resolving an un-cached domain name?",
            "How does a recursive DNS resolver locate the authoritative IP address for a fully qualified domain name?",
            "What are the hierarchical stages of recursive DNS lookups starting from root?"
        ],
        "sufficient_passages": [
            "A DNS recursive resolver queries a DNS root nameserver first, which refers it to the Top-Level Domain (TLD) nameserver, which then refers it to the authoritative nameserver that holds the final IP address mapping.",
            "To resolve an un-cached hostname, the recursive resolver queries: 1. Root server ('.'), 2. TLD server (e.g., '.com'), and 3. Authoritative server, which returns the final resource record."
        ],
        "partial_passages": [
            "The Domain Name System (DNS) is a hierarchical distributed naming system that translates human-readable domain names into numerical IP addresses.",
            "DNS resolvers maintain local caches with time-to-live (TTL) counters to minimize latency and reduce query volume to authoritative nameservers."
        ],
        "q_contradictory": [
            "Does a recursive DNS resolver query the authoritative nameserver first before querying the root or TLD servers?",
            "Does DNS recursive resolution query client web browsers to discover upstream domain IP addresses?"
        ],
        "contradictory_passages": [
            "A recursive DNS resolver queries the authoritative nameserver first without contacting root or TLD servers, reversing hierarchical resolution order.",
            "During recursive DNS resolution, external nameservers query the user's web browser local storage to discover internet IP addresses."
        ],
        "q_unverifiable": [
            "Will DNS over HTTPS (DoH) be adopted by 100% of global internet traffic by 2028?",
            "Is DNS the most fragile protocol in the entire internet protocol suite?"
        ],
        "unverifiable_passages": [
            "Global adoption rates for encrypted DNS protocols like DoH and DoT depend on enterprise filtering policies and regulatory mandates.",
            "Characterizing DNS as 'the most fragile protocol' reflects an engineering opinion rather than a measurable metric."
        ]
    }
]

# Shared pool of unrelated cross-domain distractors for IRRELEVANT class
IRRELEVANT_PASSAGES = [
    "A Gaussian blur filter applies a 2D Gaussian distribution kernel to smooth images and attenuate high-frequency noise in computer vision preprocessing.",
    "The HTTP/2 protocol multiplexes concurrent requests over a single TCP connection using binary framing layers to eliminate head-of-line blocking.",
    "RSA public-key cryptography derives security from the computational intractability of factoring large composite integers into prime factors.",
    "Stochastic gradient descent updates neural network parameter weights in the negative gradient direction using mini-batch sample approximations.",
    "In aerodynamic VTOL aircraft engineering, quad-plane configurations decouple vertical hover lift rotors from horizontal pusher cruise motors.",
    "Under ANSI SQL standards, Read Committed isolation prevents dirty reads by acquiring short-term shared read locks during row scanning.",
    "Chlorophyll pigments in plant thylakoid membranes absorb blue and red light wavelengths while reflecting green light during photosynthesis.",
    "B-tree index reorganization maintains fill factor thresholds to optimize sequential block I/O operations across physical spinning storage drives.",
    "The transformer attention mechanism calculates scaled dot-product attention scores across query, key, and value matrices in O(N^2) complexity.",
    "Finite state automata with epsilon transitions recognize the exact same class of regular languages as deterministic finite state machines."
]

# Real In-Domain held-out test benchmarks (qa_eval_dataset + project questions)
IN_DOMAIN_RECORDS = [
    {
        "example_id": "indomain_qa_01",
        "domain": "DISTRIBUTED_SYSTEMS",
        "doc_id": "consensus.docx",
        "question": "How does the Raft consensus algorithm establish consistency across nodes?",
        "passages": ["The Raft consensus algorithm establishes consistency through replicated state machines and leader election."],
        "sufficiency_label": "SUFFICIENT",
        "label_id": 0,
        "is_abstention_expected": False,
        "provenance": "qa_eval_dataset.json#qa_01",
        "verification_status": "IN_DOMAIN_GOLD"
    },
    {
        "example_id": "indomain_qa_02",
        "domain": "DISTRIBUTED_SYSTEMS",
        "doc_id": "consensus.docx",
        "question": "How does Raft divide time during system operation?",
        "passages": ["Raft divides time into terms of arbitrary length, numbered with consecutive integers."],
        "sufficiency_label": "SUFFICIENT",
        "label_id": 0,
        "is_abstention_expected": False,
        "provenance": "qa_eval_dataset.json#qa_02",
        "verification_status": "IN_DOMAIN_GOLD"
    },
    {
        "example_id": "indomain_qa_03",
        "domain": "DISTRIBUTED_SYSTEMS",
        "doc_id": "consensus.docx",
        "question": "What are the states a server can be in according to the document?",
        "passages": ["At any given time, each server is in one of three states: leader, follower, or candidate."],
        "sufficiency_label": "SUFFICIENT",
        "label_id": 0,
        "is_abstention_expected": False,
        "provenance": "qa_eval_dataset.json#qa_03",
        "verification_status": "IN_DOMAIN_GOLD"
    },
    {
        "example_id": "indomain_qa_07_irrel",
        "domain": "GENERAL",
        "doc_id": "none",
        "question": "What is the capital of France?",
        "passages": ["The Raft consensus algorithm establishes consistency through replicated state machines."],
        "sufficiency_label": "IRRELEVANT",
        "label_id": 3,
        "is_abstention_expected": True,
        "provenance": "qa_eval_dataset.json#qa_07",
        "verification_status": "IN_DOMAIN_GOLD"
    },
    {
        "example_id": "indomain_qa_08_irrel",
        "domain": "GENERAL",
        "doc_id": "none",
        "question": "Who wrote Hamlet?",
        "passages": ["In Raft, servers communicate using remote procedure calls such as RequestVote and AppendEntries."],
        "sufficiency_label": "IRRELEVANT",
        "label_id": 3,
        "is_abstention_expected": True,
        "provenance": "qa_eval_dataset.json#qa_08",
        "verification_status": "IN_DOMAIN_GOLD"
    },
    {
        "example_id": "indomain_qa_09_irrel",
        "domain": "GENERAL",
        "doc_id": "none",
        "question": "What is the chemical formula for water?",
        "passages": ["Each term begins with an election, in which one or more candidates attempt to become leader."],
        "sufficiency_label": "IRRELEVANT",
        "label_id": 3,
        "is_abstention_expected": True,
        "provenance": "qa_eval_dataset.json#qa_09",
        "verification_status": "IN_DOMAIN_GOLD"
    },
    {
        "example_id": "indomain_quest6_arithmetic",
        "domain": "ARITHMETIC",
        "doc_id": "quest6.png",
        "question": "Given a = 10, b = 5, what is result = a + b - 23 + 40?",
        "passages": ["Question: Given a = 10; b = 5; result = a + b - 23 + 40; What is the value of result?"],
        "sufficiency_label": "SUFFICIENT",
        "label_id": 0,
        "is_abstention_expected": False,
        "provenance": "quest6.png_ocr_verified",
        "verification_status": "IN_DOMAIN_GOLD"
    },
    {
        "example_id": "indomain_quest9_dbms_norm",
        "domain": "DBMS",
        "doc_id": "quest9.png",
        "question": "Given R(A, B, C, D, E) and F = {A -> B, B -> C, C -> D, AD -> E}, what is the highest normal form?",
        "passages": ["Candidate Key is A. Since B -> C and C -> D are transitive dependencies, R satisfies 2NF."],
        "sufficiency_label": "SUFFICIENT",
        "label_id": 0,
        "is_abstention_expected": False,
        "provenance": "quest9.png_ocr_verified",
        "verification_status": "IN_DOMAIN_GOLD"
    },
    {
        "example_id": "indomain_quest8_syllogism",
        "domain": "FORMAL_LOGIC",
        "doc_id": "quest8.png",
        "question": "Given statements: Some cats are dogs. All dogs are birds. Can we conclude that all cats are birds?",
        "passages": ["Some cats are dogs. All dogs are birds. Some cats are birds, but not necessarily all cats."],
        "sufficiency_label": "CONTRADICTORY",
        "label_id": 2,
        "is_abstention_expected": True,
        "provenance": "quest8.png_syllogism_countermodel",
        "verification_status": "IN_DOMAIN_GOLD"
    },
    {
        "example_id": "indomain_track2_vtol",
        "domain": "AERONAUTICAL",
        "doc_id": "Track-2 Report.pdf",
        "question": "Why was the quad-plane hybrid VTOL configuration chosen over pure fixed-wing?",
        "passages": ["The quad-plane hybrid VTOL (four dedicated lift rotors + one pusher cruise motor) was selected as it decouples the lift and cruise systems."],
        "sufficiency_label": "SUFFICIENT",
        "label_id": 0,
        "is_abstention_expected": False,
        "provenance": "Track-2 Report.pdf#page=4",
        "verification_status": "IN_DOMAIN_GOLD"
    },
    {
        "example_id": "indomain_track2_unverifiable",
        "domain": "AERONAUTICAL",
        "doc_id": "Track-2 Report.pdf",
        "question": "Will the quad-plane drone design achieve commercial passenger airworthiness certification?",
        "passages": ["For the Track 2 theme of Aerial Surveillance and Rapid Delivery, the primary design driver is the ability to combine vertical take-off/landing flexibility with precision hover."],
        "sufficiency_label": "UNVERIFIABLE",
        "label_id": 4,
        "is_abstention_expected": True,
        "provenance": "Track-2 Report.pdf#page=3",
        "verification_status": "IN_DOMAIN_GOLD"
    },
    {
        "example_id": "indomain_track2_partial",
        "domain": "AERONAUTICAL",
        "doc_id": "Track-2 Report.pdf",
        "question": "What is the exact hover endurance time and battery discharge rate during payload release?",
        "passages": ["Hover & payload release: 20-40 s Lift rotors + winch CG stability during release."],
        "sufficiency_label": "PARTIALLY_SUFFICIENT",
        "label_id": 1,
        "is_abstention_expected": True,
        "provenance": "Track-2 Report.pdf#page=12",
        "verification_status": "IN_DOMAIN_GOLD"
    }
]


# ==============================================================================
# 2. GENERATION FUNCTION WITH ZERO SPLIT LEAKAGE
# ==============================================================================

def generate_records_from_propositions(
    propositions: List[Dict[str, Any]],
    target_count_per_topic: int,
    start_id: int,
    split_name: str
) -> Tuple[List[Dict[str, Any]], int]:
    """Generates balanced 5-class records from a topic proposition list."""
    records = []
    curr_id = start_id

    # For each proposition, generate target_count_per_topic records distributed across 5 classes
    # 5 classes: SUFFICIENT, PARTIALLY_SUFFICIENT, CONTRADICTORY, IRRELEVANT, UNVERIFIABLE
    samples_per_class = max(1, target_count_per_topic // 5)

    for prop in propositions:
        domain = prop["domain"]
        doc_id = prop["doc_id"]
        topic = prop["topic"]

        # Class 0: SUFFICIENT
        for i in range(samples_per_class):
            q = random.choice(prop["q_sufficient"])
            p = random.choice(prop["sufficient_passages"])
            # Multi-passage jointly sufficient variant
            if i % 3 == 0 and len(prop["partial_passages"]) > 0:
                passages = [random.choice(prop["partial_passages"]), p]
            else:
                passages = [p]

            records.append({
                "example_id": f"er_{split_name}_suff_{curr_id:05d}",
                "domain": domain,
                "doc_id": doc_id,
                "question": q,
                "passages": passages,
                "sufficiency_label": "SUFFICIENT",
                "label_id": 0,
                "is_abstention_expected": False,
                "provenance": f"{doc_id}#{topic}",
                "verification_status": "CONTROLLED_SYNTHETIC"
            })
            curr_id += 1

        # Class 1: PARTIALLY_SUFFICIENT
        for i in range(samples_per_class):
            q = random.choice(prop["q_sufficient"])
            p = random.choice(prop["partial_passages"])
            records.append({
                "example_id": f"er_{split_name}_part_{curr_id:05d}",
                "domain": domain,
                "doc_id": doc_id,
                "question": q,
                "passages": [p],
                "sufficiency_label": "PARTIALLY_SUFFICIENT",
                "label_id": 1,
                "is_abstention_expected": True,
                "provenance": f"{doc_id}#{topic}_ablated",
                "verification_status": "CONTROLLED_PERTURBATION"
            })
            curr_id += 1

        # Class 2: CONTRADICTORY
        for i in range(samples_per_class):
            q = random.choice(prop["q_contradictory"])
            p = random.choice(prop["contradictory_passages"])
            records.append({
                "example_id": f"er_{split_name}_contra_{curr_id:05d}",
                "domain": domain,
                "doc_id": doc_id,
                "question": q,
                "passages": [p],
                "sufficiency_label": "CONTRADICTORY",
                "label_id": 2,
                "is_abstention_expected": True,
                "provenance": f"{doc_id}#{topic}_negation",
                "verification_status": "CONTROLLED_POLARITY_INVERSION"
            })
            curr_id += 1

        # Class 3: IRRELEVANT
        for i in range(samples_per_class):
            q = random.choice(prop["q_sufficient"])
            distractor = random.choice(IRRELEVANT_PASSAGES)
            records.append({
                "example_id": f"er_{split_name}_irrel_{curr_id:05d}",
                "domain": domain,
                "doc_id": doc_id,
                "question": q,
                "passages": [distractor],
                "sufficiency_label": "IRRELEVANT",
                "label_id": 3,
                "is_abstention_expected": True,
                "provenance": "cross_domain_distractor",
                "verification_status": "CROSS_DOMAIN_DISTRACTOR"
            })
            curr_id += 1

        # Class 4: UNVERIFIABLE
        for i in range(samples_per_class):
            q = random.choice(prop["q_unverifiable"])
            p = random.choice(prop["unverifiable_passages"])
            records.append({
                "example_id": f"er_{split_name}_unver_{curr_id:05d}",
                "domain": domain,
                "doc_id": doc_id,
                "question": q,
                "passages": [p],
                "sufficiency_label": "UNVERIFIABLE",
                "label_id": 4,
                "is_abstention_expected": True,
                "provenance": f"{doc_id}#{topic}_speculative",
                "verification_status": "NON_COMMIT_PASSAGE"
            })
            curr_id += 1

    return records, curr_id


def build_setu_er_splits(
    output_dir: str = "training/datasets/SETU-ER",
    seed: int = 42
) -> Dict[str, Any]:
    random.seed(seed)
    splits_dir = os.path.join(output_dir, "splits")
    os.makedirs(splits_dir, exist_ok=True)

    # 1. Generate Train (12 topics * 130 samples per topic = 1,560 samples)
    train_records, next_id = generate_records_from_propositions(
        TRAIN_PROPOSITIONS,
        target_count_per_topic=130,
        start_id=1,
        split_name="train"
    )
    random.shuffle(train_records)

    # 2. Generate Val (4 topics * 85 samples per topic = 340 samples)
    val_records, next_id = generate_records_from_propositions(
        VAL_PROPOSITIONS,
        target_count_per_topic=85,
        start_id=next_id,
        split_name="val"
    )
    random.shuffle(val_records)

    # 3. Generate Test (4 topics * 85 samples per topic = 340 samples)
    test_records, next_id = generate_records_from_propositions(
        TEST_PROPOSITIONS,
        target_count_per_topic=85,
        start_id=next_id,
        split_name="test"
    )
    random.shuffle(test_records)

    # 4. In-Domain Benchmark (12 real held-out samples)
    test_indomain_records = list(IN_DOMAIN_RECORDS)

    splits_dict = {
        "train.jsonl": train_records,
        "val.jsonl": val_records,
        "test.jsonl": test_records,
        "test_in_domain.jsonl": test_indomain_records
    }

    manifest_splits = {}
    for fname, recs in splits_dict.items():
        out_p = os.path.join(splits_dir, fname)
        class_counts = {}
        with open(out_p, "w", encoding="utf-8") as fp:
            for r in recs:
                fp.write(json.dumps(r) + "\n")
                lbl = r["sufficiency_label"]
                class_counts[lbl] = class_counts.get(lbl, 0) + 1
        print(f"Wrote {len(recs):4d} records to {out_p} | Distribution: {class_counts}")
        manifest_splits[fname] = {
            "total_records": len(recs),
            "distribution": class_counts
        }

    total_records = sum(len(r) for r in splits_dict.values())
    manifest = {
        "dataset_name": "SETU-ER",
        "description": "Evidence Relevance & Multi-Premise Sufficiency Prediction Benchmark",
        "version": "1.1.0",
        "total_records": total_records,
        "classes": ["SUFFICIENT", "PARTIALLY_SUFFICIENT", "CONTRADICTORY", "IRRELEVANT", "UNVERIFIABLE"],
        "topic_partitioning": {
            "train_topics": [p["topic"] for p in TRAIN_PROPOSITIONS],
            "val_topics": [p["topic"] for p in VAL_PROPOSITIONS],
            "test_topics": [p["topic"] for p in TEST_PROPOSITIONS],
            "test_in_domain_sources": list(set(r["doc_id"] for r in IN_DOMAIN_RECORDS))
        },
        "splits": manifest_splits
    }

    manifest_path = os.path.join(output_dir, "dataset_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as fp:
        json.dump(manifest, fp, indent=2)

    print(f"\nSETU-ER dataset generation complete. Total records: {total_records}. Manifest saved to {manifest_path}")
    return manifest


if __name__ == "__main__":
    build_setu_er_splits()
