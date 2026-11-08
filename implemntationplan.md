Development timeline
1. Week 1 – Repository ingestion
   Foundation
   Build a system that accepts a GitHub repository URL or local project directory.
   
   Tasks:
   - Clone repositories using GitPython.
   - Walk through directory structures.
   - Identify supported programming languages.
   - Ignore .git, node_modules, virtual environments and build folders.
   - Extract file metadata.
   - Generate a repository summary.
   Deliverable: Repository scanner that produces structured JSON metadata.
   
   Learn: File systems, Git internals, subprocesses, language detection.
2. Week 2 – AST parsing engine
   
   Build the component that understands source code structurally.
   
   Tasks:
   - Learn how Abstract Syntax Trees work.
   - Integrate Tree-sitter.
   - Extract functions, classes and methods.
   - Extract function parameters and return information where available.
   - Identify imports and exported symbols.
   - Record file locations and line numbers.
   Deliverable: Code parser that converts source files into structured representations.
   
   Learn: Compiler fundamentals, lexical analysis, parsing, AST traversal.
3. Week 3 – Dependency graph engine
   
   Turn the extracted code information into a graph.
   
   Tasks:
   - Create file-level dependency graphs.
   - Create function-level call graphs.
   - Map class inheritance.
   - Map function-to-function relationships.
   - Detect circular imports.
   - Calculate in-degree and out-degree.
   Deliverable: Interactive graph-ready JSON containing repository relationships.
   
   Learn: Graph theory, directed graphs, graph traversal, NetworkX.
4. Week 4 – Code complexity and architecture analysis
   
   Start extracting meaningful engineering insights.
   
   Tasks:
   - Calculate cyclomatic complexity.
   - Calculate lines of code.
   - Identify highly connected modules.
   - Detect large and highly coupled files.
   - Calculate graph centrality.
   - Identify potential architectural bottlenecks.
   Deliverable: Architecture analysis report.
   
   Learn: Software metrics, graph algorithms, software architecture.
5. Week 5 – Git history intelligence
   
   Give CodeDNA the ability to understand how the repository has evolved.
   
   Tasks:
   - Extract commit histories.
   - Identify frequently modified files.
   - Track contributors.
   - Analyze co-changing files.
   - Identify files repeatedly modified together.
   - Track changes to functions and classes across commits.
   Deliverable: Repository evolution analyzer.
   
   Learn: Git objects, commit DAGs, version control internals, temporal data analysis.
6. Week 6 – Change impact analysis
   Signature feature
   This is where the project becomes especially interesting.
   
   Example: A developer modifies authenticate_user().
   
   CodeDNA should identify:
   - Which functions call it?
   - Which modules depend on those functions?
   - Which tests might be affected?
   - Which other files historically change alongside it?
   - Which components should be reviewed before merging?
   Deliverable: Change impact report with ranked affected components.
   
   Learn: Graph traversal, dependency propagation, risk scoring, static analysis.
7. Week 7 – Bug prediction and risk engine
   
   Develop a heuristic model to identify potentially risky modules.
   
   Possible features:
   - Code complexity.
   - Change frequency.
   - Number of contributors.
   - Dependency centrality.
   - Historical bug-fix commits.
   - Code churn.
   Start with a transparent weighted scoring model. Later, compare it with a machine learning model.
   
   Deliverable: Risk-ranked modules with explanations.
   
   Learn: Feature engineering, classification, model evaluation, statistical analysis.
   
   Important: Treat these scores as investigation priorities, not proof that a file contains a bug.
8. Week 8 – FastAPI backend
   
   Convert your analysis engine into a proper application.
   
   Tasks:
   - Repository registration endpoints.
   - Analysis job endpoints.
   - Graph retrieval endpoints.
   - Module risk endpoints.
   - Change impact endpoints.
   - Database integration.
   - Background processing for large repositories.
   Deliverable: Fully functional backend API.
   
   Learn: REST architecture, asynchronous processing, database design, API validation.
9. Week 9 – React dashboard
   
   Build the visual interface.
   
   Main screens:
   - Repository overview.
   - File explorer.
   - Dependency graph.
   - Function call graph.
   - Git history timeline.
   - Risk heatmap.
   - Change impact explorer.
   Deliverable: A working web application.
   
   Learn: React, TypeScript, graph visualization, frontend-backend integration.
10. Week 10 – Testing, deployment and documentation
    
    Tasks:
    - Write unit and integration tests.
    - Test against real repositories.
    - Benchmark parsing performance.
    - Optimize large graph operations.
    - Containerize with Docker.
    - Deploy the application.
    - Create architecture diagrams and a demo video.
    - Document limitations and future work.
    Deliverable: Public GitHub repository and deployed demonstration.