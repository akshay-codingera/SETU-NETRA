"""
taxonomy.py: Hierarchical domain catalogue with natural-language descriptions.

Why this file exists:
Open-vocabulary domain classification compares text against natural-language descriptions
rather than brittle keyword sets. This file defines a multi-tiered academic and scientific
taxonomy covering computer science, mathematics, physical and biological sciences,
interdisciplinary fields, and social sciences.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class DomainDefinition:
    """Natural-language description and metadata for an academic/scientific domain."""

    domain_id: str
    domain_name: str
    hierarchy_path: Tuple[str, ...]
    description: str
    representative_concepts: Tuple[str, ...] = field(default_factory=tuple)


# Standard academic domain catalogue
DEFAULT_DOMAINS: List[DomainDefinition] = [
    # --------------------------------------------------------------------------
    # Computing -> Computer Science
    # --------------------------------------------------------------------------
    DomainDefinition(
        domain_id="cs_algorithms",
        domain_name="Algorithms & Computational Complexity",
        hierarchy_path=("Computing", "Computer Science", "Algorithms & Computational Complexity"),
        description=(
            "The study of algorithmic efficiency, running time, computational complexity, "
            "asymptotic analysis, Big-O notation, time bounds, space complexity, dynamic programming, "
            "divide and conquer, sorting algorithms, graph traversal, greedy heuristics, and NP-completeness."
        ),
        representative_concepts=(
            "computational complexity", "time complexity", "big-o", "asymptotic bound",
            "worst-case runtime", "dynamic programming", "graph traversal", "space complexity",
            "sorting", "sorting algorithm", "search algorithm", "running time"
        ),
    ),
    DomainDefinition(
        domain_id="cs_ai_ml",
        domain_name="Artificial Intelligence & Machine Learning",
        hierarchy_path=("Computing", "Computer Science", "Artificial Intelligence & Machine Learning"),
        description=(
            "The study of statistical learning algorithms, artificial neural networks, deep learning, "
            "supervised and unsupervised learning, training accuracy, test accuracy, loss functions, "
            "gradient descent, backpropagation, classification, regression, natural language processing, "
            "computer vision, reinforcement learning, and model generalization."
        ),
        representative_concepts=(
            "neural network", "machine learning", "deep learning", "training accuracy",
            "test accuracy", "gradient descent", "classification", "loss function"
        ),
    ),
    DomainDefinition(
        domain_id="cs_systems",
        domain_name="Operating Systems & Computer Architecture",
        hierarchy_path=("Computing", "Computer Science", "Operating Systems & Computer Architecture"),
        description=(
            "The study of computer hardware architectures, operating system kernels, CPU scheduling, "
            "process management, virtual memory hierarchy, paging, system calls, concurrency, threads, "
            "mutexes, device drivers, I/O management, and low-level system design."
        ),
        representative_concepts=(
            "operating system", "os kernel", "cpu scheduling", "virtual memory",
            "process management", "system call", "concurrency", "paging"
        ),
    ),
    DomainDefinition(
        domain_id="cs_databases",
        domain_name="Database Systems",
        hierarchy_path=("Computing", "Computer Science", "Database Systems"),
        description=(
            "The study of relational and non-relational database models, relational schema design, "
            "SQL queries, database normalization (1NF, 2NF, 3NF, BCNF), indexing, B-trees, "
            "ACID transaction properties, query optimization, and persistent storage management."
        ),
        representative_concepts=(
            "database normalization", "sql", "relational model", "b-tree index",
            "acid transactions", "schema design", "query optimization", "bcnf",
            "normal form", "relational table", "redundancy", "normalization"
        ),
    ),
    DomainDefinition(
        domain_id="cs_networking",
        domain_name="Computer Networks",
        hierarchy_path=("Computing", "Computer Science", "Computer Networks"),
        description=(
            "The study of computer networking protocols, the OSI model, TCP/IP stack, "
            "connection-oriented transmission (TCP), connectionless transport (UDP), routing algorithms, "
            "packet switching, network latency, IP addressing, DNS, and socket programming."
        ),
        representative_concepts=(
            "tcp", "udp", "osi model", "packet switching", "routing protocol",
            "ip address", "network latency", "socket programming", "transport layer",
            "connection-oriented", "reliable packet delivery", "protocol"
        ),
    ),
    DomainDefinition(
        domain_id="cs_cryptography",
        domain_name="Cryptography & Information Security",
        hierarchy_path=("Computing", "Computer Science", "Cryptography & Information Security"),
        description=(
            "The study of cryptographic protocols, data encryption, decryption algorithms, ciphers, "
            "symmetric key encryption (AES), asymmetric public-key cryptography (RSA, ECC), "
            "cryptographic hashing (SHA-256), message digests, digital signatures, authentication, and security."
        ),
        representative_concepts=(
            "encryption", "decryption", "cryptographic hash", "cipher", "public key",
            "digital signature", "sha-256", "rsa", "aes"
        ),
    ),

    # --------------------------------------------------------------------------
    # Mathematics
    # --------------------------------------------------------------------------
    DomainDefinition(
        domain_id="math_linear_algebra",
        domain_name="Linear Algebra",
        hierarchy_path=("Mathematics", "Linear Algebra"),
        description=(
            "The study of vector spaces, matrices, matrix multiplication, linear transformations, "
            "determinants, eigenvalues and eigenvectors, singular value decomposition, null space, "
            "rank-nullity theorem, and dot products."
        ),
        representative_concepts=(
            "vector space", "matrix multiplication", "eigenvalue", "eigenvector",
            "linear transformation", "determinant", "null space", "svd"
        ),
    ),
    DomainDefinition(
        domain_id="math_calculus",
        domain_name="Calculus & Mathematical Analysis",
        hierarchy_path=("Mathematics", "Calculus & Mathematical Analysis"),
        description=(
            "The study of continuous change, functions, limits, derivatives, differentiation rules, "
            "integrals, multivariable calculus, Taylor series, differential equations, and vector calculus."
        ),
        representative_concepts=(
            "derivative", "integral", "limit", "differential equation",
            "chain rule", "partial derivative", "taylor series"
        ),
    ),
    DomainDefinition(
        domain_id="math_statistics",
        domain_name="Probability & Statistics",
        hierarchy_path=("Mathematics", "Probability & Statistics"),
        description=(
            "The study of probability distributions, random variables, statistical expectation, "
            "variance, hypothesis testing, p-values, linear regression, statistical correlation, "
            "causation, Bayesian inference, and estimation theory."
        ),
        representative_concepts=(
            "probability distribution", "random variable", "variance", "hypothesis testing",
            "correlation", "causation", "linear regression", "bayesian inference"
        ),
    ),

    # --------------------------------------------------------------------------
    # Interdisciplinary: Signal & Image Processing
    # --------------------------------------------------------------------------
    DomainDefinition(
        domain_id="inter_image_processing",
        domain_name="Signal & Digital Image Processing",
        hierarchy_path=("Interdisciplinary", "Signal & Digital Image Processing"),
        description=(
            "The study of digital signal and image processing, 2D convolution, spatial filtering, "
            "convolutional kernel filters, image dimensions H and W, kernel size K, stride, padding, "
            "Fourier transform, frequency domain filtering, edge detection, and image enhancement."
        ),
        representative_concepts=(
            "2d convolution", "spatial filtering", "convolutional kernel", "stride",
            "image processing", "fourier transform", "edge detection", "filter kernel"
        ),
    ),

    # --------------------------------------------------------------------------
    # Social Sciences & Civics
    # --------------------------------------------------------------------------
    DomainDefinition(
        domain_id="social_civics_governance",
        domain_name="Political Science, Civics & Governance",
        hierarchy_path=("Social Sciences", "Political Science, Civics & Governance"),
        description=(
            "The study of governance, national leadership, heads of state, prime ministers, presidents, "
            "parliamentary democracy, constitutions, elections, political leaders, cabinets, and public administration."
        ),
        representative_concepts=(
            "prime minister", "president", "government", "parliament",
            "constitution", "democracy", "head of state", "cabinet"
        ),
    ),

    # --------------------------------------------------------------------------
    # Biological Sciences
    # --------------------------------------------------------------------------
    DomainDefinition(
        domain_id="bio_cellular_genetics",
        domain_name="Cellular Biology & Genetics",
        hierarchy_path=("Biological Sciences", "Cellular Biology & Genetics"),
        description=(
            "The study of living cells, cellular membranes, organelles, cytoplasm, DNA replication, "
            "RNA transcription, genetic mutations, chromosomes, cell division, and molecular genetics."
        ),
        representative_concepts=(
            "biological cell", "cell membrane", "dna", "rna",
            "gene expression", "chromosome", "organelle", "mitochondria",
            "phospholipid bilayer", "cell structure", "cellular"
        ),
    ),
]


class DomainTaxonomy:
    """Extensible registry and query engine for domain definitions."""

    def __init__(self, domains: List[DomainDefinition] | None = None):
        self._domains: Dict[str, DomainDefinition] = {}
        initial = domains if domains is not None else DEFAULT_DOMAINS
        for d in initial:
            self._domains[d.domain_id] = d

    def register_domain(self, domain: DomainDefinition) -> None:
        """Add or update a domain in the catalogue."""
        self._domains[domain.domain_id] = domain

    def get_domain(self, domain_id: str) -> DomainDefinition | None:
        return self._domains.get(domain_id)

    def list_domains(self) -> List[DomainDefinition]:
        return list(self._domains.values())

    def get_descriptions_mapping(self) -> Dict[str, str]:
        """Return mapping of domain_id to descriptive text for embedding indexing."""
        return {d_id: d.description for d_id, d in self._domains.items()}
