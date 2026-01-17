"""Topic normalizer with hybrid taxonomy.

Primary categories are normalized for consistent filtering.
Original tags are preserved for full-text search.
"""

# Primary taxonomy categories
PRIMARY_CATEGORIES = {
    "frontend",
    "backend",
    "fullstack",
    "mobile",
    "devops",
    "cloud",
    "ai-ml",
    "data",
    "security",
    "design",
    "architecture",
    "languages",
    "testing",
    "agile",
    "leadership",
    "career",
    "open-source",
    "gaming",
    "iot",
    "blockchain",
}

# Map raw tags to normalized categories
TAG_MAPPINGS: dict[str, list[str]] = {
    # Frontend
    "frontend": ["frontend"],
    "front-end": ["frontend"],
    "front end": ["frontend"],
    "ui": ["frontend", "design"],
    "ux": ["frontend", "design"],
    "css": ["frontend"],
    "html": ["frontend"],
    "javascript": ["frontend", "languages"],
    "typescript": ["frontend", "languages"],
    "react": ["frontend"],
    "reactjs": ["frontend"],
    "react.js": ["frontend"],
    "vue": ["frontend"],
    "vuejs": ["frontend"],
    "vue.js": ["frontend"],
    "angular": ["frontend"],
    "svelte": ["frontend"],
    "nextjs": ["frontend"],
    "next.js": ["frontend"],
    "web": ["frontend"],
    "web development": ["frontend"],
    "browser": ["frontend"],
    "pwa": ["frontend", "mobile"],
    "accessibility": ["frontend", "design"],
    "a11y": ["frontend", "design"],
    "genui": ["frontend", "ai-ml", "design"],
    "generative ui": ["frontend", "ai-ml", "design"],

    # Backend
    "backend": ["backend"],
    "back-end": ["backend"],
    "back end": ["backend"],
    "api": ["backend"],
    "apis": ["backend"],
    "rest": ["backend"],
    "graphql": ["backend"],
    "grpc": ["backend"],
    "microservices": ["backend", "architecture"],
    "node": ["backend"],
    "nodejs": ["backend"],
    "node.js": ["backend"],
    "express": ["backend"],
    "fastapi": ["backend"],
    "django": ["backend"],
    "flask": ["backend"],
    "rails": ["backend"],
    "ruby on rails": ["backend"],
    "spring": ["backend"],
    "spring boot": ["backend"],

    # Fullstack
    "fullstack": ["fullstack"],
    "full-stack": ["fullstack"],
    "full stack": ["fullstack"],

    # Mobile
    "mobile": ["mobile"],
    "ios": ["mobile"],
    "android": ["mobile"],
    "react native": ["mobile", "frontend"],
    "flutter": ["mobile"],
    "swift": ["mobile", "languages"],
    "kotlin": ["mobile", "languages"],

    # DevOps
    "devops": ["devops"],
    "dev ops": ["devops"],
    "ci/cd": ["devops"],
    "cicd": ["devops"],
    "docker": ["devops", "cloud"],
    "containers": ["devops", "cloud"],
    "kubernetes": ["devops", "cloud"],
    "k8s": ["devops", "cloud"],
    "helm": ["devops", "cloud"],
    "terraform": ["devops", "cloud"],
    "ansible": ["devops"],
    "jenkins": ["devops"],
    "github actions": ["devops"],
    "gitlab": ["devops"],
    "infrastructure": ["devops", "cloud"],
    "sre": ["devops"],
    "site reliability": ["devops"],
    "observability": ["devops"],
    "monitoring": ["devops"],
    "logging": ["devops"],
    "platform engineering": ["devops", "architecture"],

    # Cloud
    "cloud": ["cloud"],
    "cloud native": ["cloud"],
    "cloud-native": ["cloud"],
    "aws": ["cloud"],
    "azure": ["cloud"],
    "gcp": ["cloud"],
    "google cloud": ["cloud"],
    "serverless": ["cloud"],
    "lambda": ["cloud"],
    "cloud functions": ["cloud"],

    # AI/ML
    "ai": ["ai-ml"],
    "artificial intelligence": ["ai-ml"],
    "ml": ["ai-ml"],
    "machine learning": ["ai-ml"],
    "deep learning": ["ai-ml"],
    "neural networks": ["ai-ml"],
    "nlp": ["ai-ml"],
    "natural language processing": ["ai-ml"],
    "llm": ["ai-ml"],
    "large language models": ["ai-ml"],
    "generative ai": ["ai-ml"],
    "gen ai": ["ai-ml"],
    "chatgpt": ["ai-ml"],
    "gpt": ["ai-ml"],
    "langchain": ["ai-ml"],
    "rag": ["ai-ml"],
    "vector databases": ["ai-ml", "data"],
    "computer vision": ["ai-ml"],
    "tensorflow": ["ai-ml"],
    "pytorch": ["ai-ml"],
    "agents": ["ai-ml"],
    "ai agents": ["ai-ml"],

    # Data
    "data": ["data"],
    "data engineering": ["data"],
    "data science": ["data", "ai-ml"],
    "analytics": ["data"],
    "database": ["data"],
    "databases": ["data"],
    "sql": ["data"],
    "nosql": ["data"],
    "postgresql": ["data"],
    "postgres": ["data"],
    "mysql": ["data"],
    "mongodb": ["data"],
    "redis": ["data"],
    "elasticsearch": ["data"],
    "kafka": ["data"],
    "streaming": ["data"],
    "big data": ["data"],
    "spark": ["data"],
    "etl": ["data"],
    "data pipeline": ["data"],

    # Security
    "security": ["security"],
    "cybersecurity": ["security"],
    "cyber security": ["security"],
    "appsec": ["security"],
    "application security": ["security"],
    "devsecops": ["security", "devops"],
    "penetration testing": ["security"],
    "pentest": ["security"],
    "owasp": ["security"],
    "authentication": ["security"],
    "authorization": ["security"],
    "oauth": ["security"],
    "identity": ["security"],

    # Design & Patterns
    "design": ["design"],
    "design patterns": ["design", "architecture"],
    "patterns": ["design", "architecture"],
    "design systems": ["design", "frontend"],
    "component libraries": ["design", "frontend"],
    "figma": ["design"],
    "user experience": ["design"],
    "user interface": ["design"],
    "product design": ["design"],

    # Architecture
    "architecture": ["architecture"],
    "software architecture": ["architecture"],
    "system design": ["architecture"],
    "distributed systems": ["architecture"],
    "event-driven": ["architecture"],
    "event sourcing": ["architecture"],
    "cqrs": ["architecture"],
    "ddd": ["architecture"],
    "domain-driven design": ["architecture"],
    "clean architecture": ["architecture"],
    "hexagonal": ["architecture"],
    "modular monolith": ["architecture"],
    "monolith": ["architecture"],
    "scalability": ["architecture"],
    "performance": ["architecture"],

    # Languages
    "python": ["languages"],
    "java": ["languages"],
    "go": ["languages"],
    "golang": ["languages"],
    "rust": ["languages"],
    "c#": ["languages"],
    "csharp": ["languages"],
    ".net": ["languages"],
    "dotnet": ["languages"],
    "ruby": ["languages"],
    "php": ["languages"],
    "scala": ["languages"],
    "elixir": ["languages"],
    "erlang": ["languages"],
    "haskell": ["languages"],
    "clojure": ["languages"],
    "c++": ["languages"],
    "cpp": ["languages"],
    "c": ["languages"],
    "zig": ["languages"],
    "wasm": ["languages", "frontend"],
    "webassembly": ["languages", "frontend"],

    # Testing
    "testing": ["testing"],
    "test": ["testing"],
    "tdd": ["testing"],
    "bdd": ["testing"],
    "unit testing": ["testing"],
    "integration testing": ["testing"],
    "e2e": ["testing"],
    "end-to-end": ["testing"],
    "playwright": ["testing"],
    "cypress": ["testing"],
    "jest": ["testing"],
    "selenium": ["testing"],
    "qa": ["testing"],
    "quality assurance": ["testing"],

    # Agile & Process
    "agile": ["agile"],
    "scrum": ["agile"],
    "kanban": ["agile"],
    "lean": ["agile"],
    "product management": ["agile", "leadership"],
    "project management": ["agile", "leadership"],

    # Leadership & Career
    "leadership": ["leadership"],
    "management": ["leadership"],
    "engineering management": ["leadership"],
    "tech lead": ["leadership"],
    "team building": ["leadership"],
    "career": ["career"],
    "career development": ["career"],
    "mentoring": ["career", "leadership"],
    "soft skills": ["career"],
    "communication": ["career"],
    "public speaking": ["career"],

    # Open Source
    "open source": ["open-source"],
    "open-source": ["open-source"],
    "oss": ["open-source"],
    "community": ["open-source"],
    "contributing": ["open-source"],

    # Gaming
    "gaming": ["gaming"],
    "game development": ["gaming"],
    "game dev": ["gaming"],
    "unity": ["gaming"],
    "unreal": ["gaming"],
    "godot": ["gaming"],

    # IoT
    "iot": ["iot"],
    "internet of things": ["iot"],
    "embedded": ["iot"],
    "raspberry pi": ["iot"],
    "arduino": ["iot"],
    "hardware": ["iot"],

    # Blockchain
    "blockchain": ["blockchain"],
    "web3": ["blockchain"],
    "crypto": ["blockchain"],
    "ethereum": ["blockchain"],
    "solidity": ["blockchain"],
    "smart contracts": ["blockchain"],
    "defi": ["blockchain"],
    "nft": ["blockchain"],
}


def normalize_tag(tag: str) -> str:
    """Normalize a single tag to lowercase, trimmed."""
    return tag.lower().strip()


def map_to_categories(tags: list[str]) -> list[str]:
    """Map raw tags to normalized primary categories."""
    categories = set()

    for tag in tags:
        normalized = normalize_tag(tag)
        if normalized in TAG_MAPPINGS:
            categories.update(TAG_MAPPINGS[normalized])
        # Also check if the tag itself is a primary category
        elif normalized in PRIMARY_CATEGORIES:
            categories.add(normalized)

    return sorted(categories)


def normalize_topics(raw_tags: list[str]) -> tuple[list[str], list[str]]:
    """Normalize topics using hybrid approach.

    Returns:
        Tuple of (original_tags_cleaned, normalized_categories)
    """
    # Clean original tags (keep for search)
    cleaned = [tag.strip() for tag in raw_tags if tag.strip()]

    # Map to categories
    categories = map_to_categories(raw_tags)

    return cleaned, categories
