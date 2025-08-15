# called inside kto.py::train_model

import argparse
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import KTOConfig, KTOTrainer


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_name", type=str, required=True)
    parser.add_argument("--train_file", type=str, required=True)
    parser.add_argument("--eval_file", type=str, required=True)
    parser.add_argument("--model_name_or_path", type=str, required=True)
    parser.add_argument("--save_dir", type=str, required=True)
    parser.add_argument("--max_steps", type=int, required=True)
    parser.add_argument("--beta", type=float, required=True)
    parser.add_argument("--lr", type=float, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()

    dataset = load_dataset(
        "parquet",
        data_files={
            "train": args.train_file,
            "test": args.eval_file,
        },
    )
    train_dataset = dataset["train"]
    val_dataset = dataset["test"]

    model = AutoModelForCausalLM.from_pretrained(
        args.model_name_or_path,
        torch_dtype=torch.bfloat16,
    )
    tokenizer = AutoTokenizer.from_pretrained(args.model_name_or_path)

    resume_path = None
    if args.resume:
        save_dir = Path(args.save_dir)
        candidates = [
            d
            for d in save_dir.iterdir()
            if d.is_dir() and d.name.startswith("checkpoint-")
        ]
        if candidates:
            candidates.sort(
                key=lambda p: (
                    int(p.name.split("checkpoint-")[-1]),
                    p.stat().st_mtime,
                )
            )
            resume_path = str(candidates[-1])

    # hyperparameters
    # https://huggingface.co/docs/trl/main/en/kto_trainer#usage-tips

    max_length = 2048
    max_completion_length = 32
    max_prompt_length = max_length - max_completion_length

    batch_size_per_device = 8
    gradient_accumulation_steps = 4

    lr_scheduler_type = "cosine"
    warmup_ratio = 0.1

    n_chosen = train_dataset.filter(lambda x: x["label"]).num_rows
    n_rejected = train_dataset.filter(lambda x: not x["label"]).num_rows
    print(f"n_chosen: {n_chosen}, n_rejected: {n_rejected}")

    data_ratio = n_chosen / n_rejected
    target_max_ratio = 4.0 / 3.0

    if data_ratio > target_max_ratio:  # too many chosen examples, upweight rejected
        desirable_weight = 1.0
        undesirable_weight = data_ratio / target_max_ratio
    elif data_ratio < 1.0:  # too many rejected examples, upweight chosen
        desirable_weight = 1.0 / data_ratio
        undesirable_weight = 1.0
    else:
        desirable_weight = 1.0
        undesirable_weight = 1.0

    print(
        f"desirable_weight: {desirable_weight:.3f}, undesirable_weight: {undesirable_weight:.3f}"
    )
    weighted_ratio = (desirable_weight * n_chosen) / (undesirable_weight * n_rejected)
    print(f"weighted ratio: {weighted_ratio:.3f} (target: 1.0 to 1.33)")

    # start training

    log_steps = 10
    eval_steps = args.max_steps // 10

    training_args = KTOConfig(
        max_length=max_length,
        max_prompt_length=max_prompt_length,
        max_completion_length=max_completion_length,
        # kto
        beta=args.beta,
        desirable_weight=desirable_weight,
        undesirable_weight=undesirable_weight,
        # hp
        max_steps=args.max_steps,
        per_device_train_batch_size=batch_size_per_device,
        gradient_accumulation_steps=gradient_accumulation_steps,
        learning_rate=args.lr,
        lr_scheduler_type=lr_scheduler_type,
        warmup_ratio=warmup_ratio,
        bf16=True,
        # eval
        eval_strategy="steps",
        eval_steps=eval_steps,
        per_device_eval_batch_size=batch_size_per_device,
        # wandb
        report_to="wandb",
        run_name=args.run_name,
        logging_steps=log_steps,
        # ckpt
        output_dir=args.save_dir,
        # misc
        seed=args.seed,
        remove_unused_columns=False,
    )

    trainer = KTOTrainer(
        model=model,
        args=training_args,
        processing_class=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
    )

    trainer.train(
        resume_from_checkpoint=resume_path,
    )


if __name__ == "__main__":
    main()
