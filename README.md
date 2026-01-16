# DevTools Review Forge ⚒️

A sophisticated, agentic synthetic data generator for Developer Tools reviews. This system creates high-quality, diverse, and realistically biased reviews for **VS Code** by simulating specific user personas and enforcing strict quality guardrails.

## 🚀 Features

- **Agentic Workflow**: Uses [LangGraph](https://langchain-ai.github.io/langgraph/) to orchestrate a cyclic generation-judgment loop.
- **Multi-Persona Generation**: Simulates different user types (e.g., "Technical Reviewer", "Frustrated Newbie") to ensure data diversity.
- **Quality Guardrails**:
  - **Diversity Check**: Jaccard similarity metrics prevent repetitive outputs.
  - **Bias & Realism**: An LLM-based Judge rejects "marketing-speak" or hallucinatory features.
  - **Likert Scoring**: Assigns a 1-10 quality score to every accepted review.
- **Robustness**:
  - **Model Fallback**: Automatically retries with a backup model (e.g., Mistral) if the primary model fails.
  - **Incremental Saving**: Saves progress after every rating batch to prevent data loss.
- **Configurable**: Fully driven by `config/default.yaml`—change models, prompts, and distributions without touching code.

## 🛠️ Setup

### Prerequisites
- Python 3.9+
- OpenAI API Key (or OpenRouter)

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repo-url>
   cd devtools-review-forge
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   Create a `.env` file in the root directory:
   ```bash
   OPENAI_API_KEY=sk-...
   # OR
   OPENROUTER_API_KEY=sk-or-...
   ```

4. **Prepare Data (Optional)**:
   The system comes with `data/real_reviews_capterra.csv`. If you want to scrape fresh data:
   ```bash
   python -m src.collector.scrape_capterra
   ```

### Configuration
Edit `config/default.yaml` to customize:
- **Models**: Primary and Rollback models for Generator/Judge.
- **Personas**: Define who is writing the review.
- **Rating Distribution**: Set the % of 1-star vs 5-star reviews.
- **Review Characteristics**: Add specific tones or focus topics (e.g., "Pricing", "Extensions").

## 🏃‍♂️ Usage

Run the main workflow:
```bash
python -m src.main
```

Follow the interactive prompt:
```text
Total Number of Reviews Needed (Approx): 50
```

The system will:
1.  Iterate through 1-star to 5-star ratings based on your distribution.
2.  Generate batches of reviews.
3.  **Judge** them against real ground-truth data.
4.  **Filter** out spam, duplicates, or unrealistic samples.
5.  Save accepted reviews to `data/generated_reviews.csv`.
6.  Print a final report with timing and yield metrics.

## 🏗️ Design Decisions

### 1. Agentic Architecture (LangGraph)
We chose **LangGraph** over simple linear scripts or purely prompt-based approaches.
- **Why?** Real-world generation requires feedback loops. If a batch of reviews is rejected for being "too generic," the system needs to know *why* and retry. LangGraph allows us to model this stateful, cyclic flow (Generate -> Judge -> Filter -> Loop or End).

### 2. Separation of Concerns (Generator vs. Judge)
- **Generator**: Optimized for creativity and persona adoption. It "hallucinates" believable user experiences.
- **Judge**: Optimized for critical analysis. It compares the output against *actual* Capterra reviews to detect subtle stylistic mismatches.
- **Benefit**: This Adversarial-like setup improves quality significantly compared to self-correction by a single agent.

### 3. Configuration-Driven Development
- **Why?** Hardcoding prompts or model names makes experiments painful.
- **Decision**: All volatile parameters (prompts, models, file paths, fallback logic) are externalized to `config/default.yaml`. This allows non-coders to tweak the "personality" of the dataset.

## ⚖️ Trade-offs

### Latency vs. Quality
- **Trade-off**: The "Judge-Filter-Retry" loop significantly increases the time-per-review compared to raw generation.
- **Decision**: We prioritized **Quality**. A dataset of 100 perfectly realistic reviews is more valuable for training/testing than 1000 obvious AI slop reviews.
- **Mitigation**: We implemented `cumulative_generated` tracking and a Final Report to give users visibility into the "cost" of quality (e.g., "7 Generated to get 5 Accepted").

### Cost
- **Trade-off**: Running two LLM calls (Generation + Judgment) per output doubles inference costs.
- **Decision**: Acceptable for synthetic data generation where the volume is typically in the thousands, not millions. The use of cheaper "Rollback" models (like `mistralai/devstral`) helps mitigate this when the primary model is unavailable or too expensive.

### Complexity
- **Trade-off**: Testing a stateful graph is harder than testing a function.
- **Decision**: We implemented unit tests for specific components (guardrails) and a robust `should_continue` logic to prevent infinite recursion, accepting higher architectural complexity for better resilience.

## 🔮 Future Work
- **topic_distribution**: Enforce specific percentages for topics (e.g., ensure 20% of reviews mention "Python").
- **Dynamic Few-Shot**: Retreive the *most similar* real reviews to the target persona dynamically using RAG, rather than random sampling.