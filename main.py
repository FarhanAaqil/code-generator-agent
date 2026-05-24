#!/usr/bin/env python3
"""
Self-Improving Code Agent — CLI entry point
Usage: python main.py "Write a function that finds prime numbers up to n"
"""
import sys
import argparse
from config import GROQ_API_KEY, MODEL, MAX_RETRIES, MAX_CRITIQUE_ROUNDS
from generator import run_generator_loop
from critique import critique_code
from sandbox import run_code
from benchmark import benchmark_code, compare, log_benchmark
from memory import (
    build_memory_context, store_failure, retrieve_similar_failures,
    CHROMADB_AVAILABLE
)


def print_separator(char="─", width=60):
    print(char * width)


def run_cli(task: str, api_key: str = None, model: str = None,
            max_retries: int = None, max_critique: int = None,
            enable_memory: bool = True, enable_critique: bool = True,
            enable_benchmark: bool = True):

    api_key = api_key or GROQ_API_KEY
    model = model or MODEL
    max_retries = max_retries or MAX_RETRIES
    max_critique = max_critique or MAX_CRITIQUE_ROUNDS

    print_separator("═")
    print("  Self-Improving Code Agent")
    print(f"  Model: {model} | Retries: {max_retries} | Critique: {max_critique}")
    print_separator("═")
    print(f"\nTask: {task}\n")

    # Phase 1: Memory Lookup
    memory_context = ""
    if enable_memory and CHROMADB_AVAILABLE:
        print_separator()
        print("Phase 1 — Memory Lookup")
        print_separator()
        failures = retrieve_similar_failures(task)
        if failures:
            print(f"  Found {len(failures)} similar past failures:")
            for f in failures:
                print(f"  [{f['similarity']:.2f}] {f['task'][:60]}...")
            memory_context = build_memory_context(task)
        else:
            print("  No similar failures found. Starting fresh.")
        print()

    # Phase 2: Generator
    print_separator()
    print("Phase 2 — Generator Agent")
    print_separator()

    current_code = None
    working_output = ""

    def on_token(t):
        print(t, end="", flush=True)

    def on_attempt_start(attempt, total):
        print(f"\nAttempt {attempt}/{total}:")
        print("  Generating code...")

    def on_attempt_result(attempt, success, code, output, error):
        nonlocal current_code, working_output
        if success:
            print(f"\n  ✓ PASSED | Output: {output[:80]}")
            current_code = code
            working_output = output
        else:
            print(f"\n  ✗ FAILED | Error: {error[:120]}")
            if enable_memory and CHROMADB_AVAILABLE:
                store_failure(task, code, error)
                print("  [Stored failure in memory]")

    gen_result = run_generator_loop(
        task=task,
        memory_context=memory_context,
        max_retries=max_retries,
        api_key_override=api_key,
        model_override=model,
        on_token=on_token,
        on_attempt_start=on_attempt_start,
        on_attempt_result=on_attempt_result
    )

    print()
    if not gen_result["success"]:
        print("\n✗ Generator failed after all retries. Exiting.")
        return

    current_code = gen_result["code"]
    working_output = gen_result["output"]
    original_code = current_code

    # Phase 3: Critique
    if enable_critique:
        print()
        print_separator()
        print("Phase 3 — Critique Agent")
        print_separator()

        for round_num in range(1, max_critique + 1):
            print(f"\nCritique Round {round_num}/{max_critique}:")
            verdict = critique_code(
                task=task,
                code=current_code,
                output=working_output,
                api_key_override=api_key,
                model_override=model
            )

            if verdict["verdict"] == "APPROVED":
                print("  ✓ APPROVED — Code passed critique review.")
                break
            elif verdict["verdict"] == "REWRITE":
                print("  ⚠ REWRITE requested")
                for issue in verdict["issues"]:
                    print(f"    - {issue}")
                print(f"  Instructions: {verdict['instructions'][:150]}")
                print("  Rewriting...")

                rewrite_result = run_generator_loop(
                    task=task,
                    rewrite_instructions=verdict["instructions"],
                    max_retries=3,
                    api_key_override=api_key,
                    model_override=model,
                    on_token=on_token
                )
                print()
                if rewrite_result["success"]:
                    current_code = rewrite_result["code"]
                    working_output = rewrite_result["output"]
                    print("  ✓ Rewrite passed sandbox validation.")
                else:
                    print("  ✗ Rewrite failed — keeping previous working version.")
                    break
            else:
                print(f"  ! Critique error: {verdict['issues']}")
                break

    # Phase 4: Benchmark
    if enable_benchmark and original_code != current_code:
        print()
        print_separator()
        print("Phase 4 — Benchmark")
        print_separator()
        print("  Benchmarking original code...")
        before = benchmark_code(original_code)
        print("  Benchmarking optimized code...")
        after = benchmark_code(current_code)

        if before["success"] and after["success"]:
            comp = compare(before, after)
            log_benchmark(task, before, after, comp)
            print(f"\n  Before: avg={before['avg_ms']:.2f}ms, mem={before['peak_kb']:.1f}KB")
            print(f"  After:  avg={after['avg_ms']:.2f}ms, mem={after['peak_kb']:.1f}KB")
            delta = comp.get("runtime_delta_pct")
            if delta is not None:
                arrow = "↑ Faster" if delta < 0 else "↓ Slower"
                print(f"  Result: {abs(delta):.1f}% {arrow}")
        else:
            print("  ⚠ Benchmark failed — skipping.")

    # Final Output
    print()
    print_separator("═")
    print("Final Result")
    print_separator("═")
    print(f"  Status: {'✓ SUCCESS' if gen_result['success'] else '✗ FAILED'}")
    print(f"  Generator attempts: {gen_result['attempts']}")
    print(f"\nFinal code:\n")
    print(current_code)
    print()


def main():
    parser = argparse.ArgumentParser(description="Self-Improving Code Agent CLI")
    parser.add_argument("task", nargs="?", default=None, help="Task description")
    parser.add_argument("--model", default=None, help="Model to use")
    parser.add_argument("--retries", type=int, default=None, help="Max fix retries")
    parser.add_argument("--critique", type=int, default=None, help="Max critique rounds")
    parser.add_argument("--no-memory", action="store_true", help="Disable vector memory")
    parser.add_argument("--no-critique", action="store_true", help="Disable critique agent")
    parser.add_argument("--no-benchmark", action="store_true", help="Disable benchmark")
    args = parser.parse_args()

    task = args.task
    if not task:
        print("Self-Improving Code Agent")
        print("Usage: python main.py \"<your task>\"")
        print("   Or: streamlit run app.py")
        return

    run_cli(
        task=task,
        model=args.model,
        max_retries=args.retries,
        max_critique=args.critique,
        enable_memory=not args.no_memory,
        enable_critique=not args.no_critique,
        enable_benchmark=not args.no_benchmark
    )


if __name__ == "__main__":
    main()
