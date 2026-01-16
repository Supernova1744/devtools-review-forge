import os
import time
import random
import pandas as pd
from langgraph.graph import StateGraph, END
from src.agents import ReviewGenerator, ReviewJudge
from src.utils.utils import load_config
from src.Models.WorkflowState import WorkflowState

config = load_config()

def get_generator():
    cfg = config.get("ReviewGenerator", {})
    return ReviewGenerator(
        model=cfg.get("model", "xiaomi/mimo-v2-flash:free"),
        rollback_model=cfg.get("rollback_model", None),
        temperature=cfg.get("temperature", 0.7),
        csv_path=cfg.get("csv_path", "data/real_reviews_capterra.csv"),
        rating_column=cfg.get("rating_column", "rating"),
        persona=cfg.get("persona", "a Technical Reviewer"),
        review_characteristics=config.get("review_characteristics", {})
    )

def get_judge():
    cfg = config.get("ReviewJudge", {})
    return ReviewJudge(
        model=cfg.get("model", "xiaomi/mimo-v2-flash:free"),
        rollback_model=cfg.get("rollback_model", None),
        temperature=cfg.get("temperature", 0.0),
        csv_path=cfg.get("csv_path", "data/real_reviews_capterra.csv"),
        rating_column=cfg.get("rating_column", "rating"),
        persona=cfg.get("persona", "an expert Review Quality Judge"),
        review_characteristics=config.get("review_characteristics", {})
    )

# --- Nodes ---

def node_generate(state: WorkflowState):
    """
    Generates usage reviews.
    Calculate how many more match 'required_count - len(accepted)'.
    """
    current_count = len(state.get("accepted_reviews", []))
    needed = state["required_count"] - current_count
    
    # Safety: if needed <= 0, we shouldn't be here, but just in case
    if needed <= 0:
        return {"current_generated_reviews": []}

    print(f"\n🌀 [Generator] Generating {needed} reviews (Iteration {state.get('iteration', 1)})...")
    
    generator = get_generator()
    # ReviewGenerator.generate_reviews now returns distinct dict or list?
    # Based on verify output: {'reviews': [...]}
    result = generator.generate_reviews(target_rating=state["target_rating"], count=needed)
    
    reviews = result.get('reviews', []) if result else []
    
    # Convert Pydantic models to dicts if they are objects
    cleaned_reviews = []
    for r in reviews:
        if hasattr(r, 'model_dump'):
            cleaned_reviews.append(r.model_dump())
        elif isinstance(r, dict):
            cleaned_reviews.append(r)
        else:
             # Fallback
            cleaned_reviews.append(dict(r))

    return {
        "current_generated_reviews": cleaned_reviews,
        "cumulative_generated": len(cleaned_reviews),
        "iteration": state.get("iteration", 0) + 1
    }

def node_judge(state: WorkflowState):
    """
    Judges the currently generated reviews.
    """
    reviews = state.get("current_generated_reviews", [])
    if not reviews:
        return {"current_judgments": []}

    print(f"⚖️ [Judge] Evaluating {len(reviews)} reviews...")
    judge = get_judge()
    judgments = judge.evaluate_reviews(reviews, target_rating=state["target_rating"])
    
    return {"current_judgments": judgments}

def node_filter(state: WorkflowState):
    """
    Filters reviews that passed judgment and adds them to accepted_reviews.
    """
    judgments = state.get("current_judgments", [])
    passed = []
    
    for item in judgments:
        verdict = item.get("judgment", {}).get("verdict", "FAIL").upper()
        if verdict == "PASS":
            review = item["review"]
            # Extract Quality Score
            quality_score = item.get("judgment", {}).get("quality_score", None)
            review["quality_score"] = quality_score
            passed.append(review)
        else:
            reason = item.get("judgment", {}).get("reason", "Unknown")
            print(f"   ❌ Rejected: {reason}")

    print(f"✅ [Filter] Accepted {len(passed)} new reviews.")
    return {"accepted_reviews": passed}

# --- Conditional Logic ---

def should_continue(state: WorkflowState):
    current_total = len(state.get("accepted_reviews", []))
    required = state["required_count"]
    
    if current_total >= required:
        print(f"🎉 Target reached! Total accepted: {current_total}")
        return END

    iteration = state.get("iteration", 0)
    MAX_RETRIES = 10
    if iteration > MAX_RETRIES:
        print(f"⚠️ Max retries ({MAX_RETRIES}) reached. Stopping early.")
        return END
    
    print(f"🔄 Need {required - current_total} more reviews. Looping back...")
    return "generate"

# --- Build Graph ---

def build_graph():
    graph = StateGraph(WorkflowState)
    
    graph.add_node("generate", node_generate)
    graph.add_node("judge", node_judge)
    graph.add_node("filter", node_filter)
    
    graph.set_entry_point("generate")
    
    graph.add_edge("generate", "judge")
    graph.add_edge("judge", "filter")
    graph.add_conditional_edges("filter", should_continue, {
        "generate": "generate",
        END: END
    })
    
    return graph.compile()

if __name__ == "__main__":
    # Interactive CLI
    print("🚀 DevTools Review Forge - Agentic Workflow")
    
    try:
        count_input = input("Total Number of Reviews Needed (Approx): ").strip()
        total_count = int(count_input)
        
        # Get distribution or default to uniform
        distribution = config.get("rating_distribution", [0.2, 0.2, 0.2, 0.2, 0.2])
        if len(distribution) != 5:
            print("⚠️ Warning: rating_distribution should have 5 values.Using default uniform.")
            distribution = [0.2, 0.2, 0.2, 0.2, 0.2]
            
        print(f"📊 Target Distribution: {distribution}")
        
        app = build_graph()
        
        
        start_time = time.time()
        all_accepted = []
        grand_total_generated = 0

        for i, ratio in enumerate(distribution):
            rating = float(i + 1)
            target_count = int(total_count * ratio)
            
            if target_count <= 0:
                continue
                
            print(f"\n" + "="*50)
            print(f"🎯 Processing Rating {rating} (Target: {target_count} reviews)")
            print("="*50)

            initial_state = {
                "target_rating": rating,
                "required_count": target_count,
                "accepted_reviews": [],
                "current_generated_reviews": [],
                "cumulative_generated": 0,
                "current_judgments": [],
                "iteration": 1
            }
            
            final_state = app.invoke(initial_state, {"recursion_limit": 50})
            accepted = final_state.get("accepted_reviews", [])
            # Enrich reviews with the target rating for tracking
            for rev in accepted:
                rev['generated_rating'] = rating
            
            grand_total_generated += final_state.get("cumulative_generated", 0)
            all_accepted.extend(accepted)
            
            # Save incrementally (append mode handled below)
            if accepted:
                df = pd.DataFrame(accepted)
                df['generated_rating'] = rating
                output_path = config.get("output_path", "data/generated_reviews.csv")
                
                # Check if file exists to determine if we need to write the header
                file_exists = os.path.isfile(output_path)
                
                df.to_csv(output_path, mode='a', header=not file_exists, index=False)
                print(f"💾 Appended {len(df)} reviews to {output_path}")

        total_duration = time.time() - start_time
        total_accepted = len(all_accepted)
        avg_time = total_duration / total_accepted if total_accepted > 0 else 0

        print("\n" + "="*50)
        print("📊 FINAL EXECUTION REPORT")
        print("="*50)
        print(f"✅ Total Accepted Reviews:  {total_accepted}")
        print(f"🔢 Total Generated Reviews: {grand_total_generated}")
        print(f"⏱️  Total Duration:        {total_duration:.2f}s")
        print(f"⚡ Time per Accepted Review: {avg_time:.2f}s")
        print("="*50)

        # --- Generate Quality Report ---
        report_path = config.get("report_path", "data/quality_report.md")
        
        # Load Real Data for Comparison
        real_csv_path = config.get("ReviewGenerator", {}).get("csv_path", "data/real_reviews_capterra.csv")
        try:
            df_real = pd.read_csv(real_csv_path)
            real_count = len(df_real)
            # Calculate avg word count for real reviews (assuming 'pros', 'cons', 'general' columns)
            # Simple approximation: combining columns
            df_real['text'] = df_real.get('general', '') + " " + df_real.get('pros', '') + " " + df_real.get('cons', '')
            real_avg_len = df_real['text'].str.split().str.len().mean()
        except Exception as e:
            print(f"⚠️ Could not load real data for comparison: {e}")
            real_count = 0
            real_avg_len = 0

        # Calculate Synthetic Metrics
        if all_accepted:
             df_synth = pd.DataFrame(all_accepted)
             synth_avg_len = (df_synth.get('general', '') + " " + df_synth.get('pros', '') + " " + df_synth.get('cons', '')).str.split().str.len().mean()
             avg_quality = df_synth['quality_score'].mean() if 'quality_score' in df_synth.columns else 0
        else:
            synth_avg_len = 0
            avg_quality = 0

        yield_rate = (total_accepted / grand_total_generated * 100) if grand_total_generated > 0 else 0

        report_content = f"""# 📊 DevTools Review Forge - Quality Report
**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}

## 1. System Performance
| Metric | Value |
| :--- | :--- |
| **Total Generated** | {grand_total_generated} |
| **Total Accepted** | {total_accepted} |
| **Yield Rate** | {yield_rate:.1f}% |
| **Execution Time** | {total_duration:.2f}s |
| **Avg Time / Review** | {avg_time:.2f}s |

## 2. Quality & Realism
| Metric | Synthetic | Real (Baseline) |
| :--- | :--- | :--- |
| **Avg Word Count** | {synth_avg_len:.0f} words | {real_avg_len:.0f} words |
| **Avg Quality Score (Judge)** | {avg_quality:.1f} / 10 | N/A |

## 3. Configuration Snapshot
- **Generator Model**: `{config.get("ReviewGenerator", {}).get("model")}`
- **Judge Model**: `{config.get("ReviewJudge", {}).get("model")}`
- **Target Distribution**: `{distribution}`

## 4. Observations
- **Yield Analysis**: A low yield rate (<50%) suggests the Generator is struggling to meet the Judge's strict criteria. Check `ReviewJudge.py` rejection reasons.
- **Length Mismatch**: Significant differences in word count may indicate the model is too verbose or too brief compared to real users.

## 5. Side-by-Side Comparison
| Rating | Real Sample | Synthetic Sample |
| :--- | :--- | :--- |
"""
        
        # Add Samples rows
        rating_col = config.get("ReviewGenerator", {}).get("rating_column", "rating")
        
        for r in range(1, 6):
            rating_val = float(r)
            
            # --- Get Real Sample ---
            real_text = "_No data_"
            if 'df_real' in locals() and not df_real.empty and rating_col in df_real.columns:
                # Ensure type matching
                try:
                    matches = df_real[df_real[rating_col].astype(float) == rating_val]
                    if not matches.empty:
                        row = matches.sample(n=1).iloc[0]
                        # Combine text fields
                        raw_text = f"{row.get('general', '')} {row.get('pros', '')} {row.get('cons', '')}"
                        # Truncate and clean for markdown table
                        clean_text = raw_text.replace('\n', ' ').replace('|', '')
                        real_text = (clean_text[:150] + '...') if len(clean_text) > 150 else clean_text
                except Exception:
                    pass

            # --- Get Synthetic Sample ---
            synth_text = "_No generated data_"
            if all_accepted:
                df_synth_all = pd.DataFrame(all_accepted)
                if 'generated_rating' in df_synth_all.columns:
                     matches = df_synth_all[df_synth_all['generated_rating'] == rating_val]
                     if not matches.empty:
                        row = matches.sample(n=1).iloc[0]
                        raw_text = f"{row.get('general', '')} {row.get('pros', '')} {row.get('cons', '')}"
                        clean_text = raw_text.replace('\n', ' ').replace('|', '')
                        synth_text = (clean_text[:150] + '...') if len(clean_text) > 150 else clean_text

            report_content += f"| **{r} Stars** | {real_text} | {synth_text} |\n"
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        
        print(f"\n📝 Quality Report saved to: {report_path}")

    except Exception as e:
        print(f"❌ Error: {e}")
