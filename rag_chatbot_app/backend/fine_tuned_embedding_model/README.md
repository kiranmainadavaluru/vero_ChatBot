---
tags:
- sentence-transformers
- sentence-similarity
- feature-extraction
- generated_from_trainer
- dataset_size:144
- loss:MultipleNegativesRankingLoss
base_model: sentence-transformers/all-MiniLM-L6-v2
widget:
- source_sentence: day 2
  sentences:
  - '### Day 4: `*args`, `**kwargs`, Unpacking

    - [ ] Learn: positional/keyword unpacking, `*`, `**` in function defs and calls

    - [ ] Solve: write a function that logs any function''s args/kwargs generically

    - [ ] Build: a flexible config-merging function using `**kwargs`

    - [ ] Interview Q: "How would you write a function that accepts unlimited arguments?"'
  - '### Day 2: Scope & Closures (LEGB rule)

    - [ ] Learn: Local → Enclosing → Global → Built-in resolution order, `nonlocal`
    vs `global`

    - [ ] Predict-then-run: nested functions with closures over a loop variable (classic
    bug)

    - [ ] Build: a counter/accumulator function using a closure (no classes)

    - [ ] Interview Q: "What''s the difference between a closure in Python and JS?"'
  - '### Day 7: Review + Build

    - [ ] Build a CLI file-organizer tool combining: comprehensions, exceptions, a
    context manager, and `*args`

    - [ ] Write 5 self-quiz questions covering Days 1-6, answer them cold (no notes)

    - [ ] Add all 6 concepts to your interview doc using the 6-part structure


    ---


    ## WEEK 2 — OOP, Decorators, Testing'
- source_sentence: day 22
  sentences:
  - '---


    ## WEEK 1 — Core Mental Models


    ### Day 1: Mutability, Identity vs Equality

    - [ ] Learn: mutable vs immutable types, `is` vs `==`, how variables reference
    objects

    - [ ] Predict-then-run: 3 snippets showing a mutable default argument bug

    - [ ] Build: a function that demonstrates the classic "mutable default arg" gotcha,
    then fix it

    - [ ] Interview Q: "Why is using a mutable default argument dangerous in Python?"'
  - '### Day 19: Static Type Checking

    - [ ] Learn: run `mypy` on your typed code, fix the errors it surfaces

    - [ ] Solve: intentionally introduce 3 type bugs, catch them with mypy before
    running

    - [ ] Interview Q: "What''s the tradeoff of using strict typing in Python?"'
  - '---


    ## WEEK 4 — Applied Mastery + Interview Reps


    ### Day 22: Plan a Harder Chatbot Feature

    - [ ] Pick one: streaming responses, async endpoint handling, or improved chunking
    strategy

    - [ ] Design it on paper first — no code yet. Write the approach in your 6-part
    doc format


    ### Day 23: Implement It (Part 1)

    - [ ] Build the core logic for the feature you planned on Day 22

    - [ ] Predict-then-run each new snippet before executing'
- source_sentence: day 6
  sentences:
  - '### Day 6: Context Managers

    - [ ] Learn: `with` statement, `__enter__`/`__exit__`, `contextlib.contextmanager`

    - [ ] Solve: write a context manager that times a code block

    - [ ] Build: a context manager that safely opens/closes a DB connection (tie to
    your PostgreSQL work)

    - [ ] Interview Q: "What problem do context managers solve that try/finally doesn''t
    solve as cleanly?"'
  - '---


    ## WEEK 4 — Applied Mastery + Interview Reps


    ### Day 22: Plan a Harder Chatbot Feature

    - [ ] Pick one: streaming responses, async endpoint handling, or improved chunking
    strategy

    - [ ] Design it on paper first — no code yet. Write the approach in your 6-part
    doc format


    ### Day 23: Implement It (Part 1)

    - [ ] Build the core logic for the feature you planned on Day 22

    - [ ] Predict-then-run each new snippet before executing'
  - '### Day 26: Timed Mock Problem — Data Structures

    - [ ] 45 min, no notes: solve 1 medium problem using dicts/sets/lists optimally

    - [ ] Review: could you explain your time/space complexity out loud?


    ### Day 27: Timed Mock Problem — Algorithms

    - [ ] 45 min, no notes: solve 1 medium problem (recursion, sorting, or search)

    - [ ] Review your solution against a clean reference solution — note gaps'
- source_sentence: what did I learn on day 19
  sentences:
  - '### Day 13: pytest Basics

    - [ ] Learn: `assert`, fixtures, `@pytest.mark.parametrize`

    - [ ] Build: write 5 tests for your `Document` classes from Days 8-12

    - [ ] Interview Q: "How do fixtures reduce duplication in test suites?" (easy
    one for you as an SDET — write your own answer anyway)'
  - '### Day 19: Static Type Checking

    - [ ] Learn: run `mypy` on your typed code, fix the errors it surfaces

    - [ ] Solve: intentionally introduce 3 type bugs, catch them with mypy before
    running

    - [ ] Interview Q: "What''s the tradeoff of using strict typing in Python?"'
  - '### Day 14: Build & Test a Real Tool

    - [ ] Build a log-parser CLI tool using everything from Week 2

    - [ ] Write a full pytest suite for it (aim for meaningful coverage, not 100%)

    - [ ] Add Week 2 concepts to your interview doc


    ---


    ## WEEK 3 — Concurrency, Typing, Packaging'
- source_sentence: day 12
  sentences:
  - '### Day 19: Static Type Checking

    - [ ] Learn: run `mypy` on your typed code, fix the errors it surfaces

    - [ ] Solve: intentionally introduce 3 type bugs, catch them with mypy before
    running

    - [ ] Interview Q: "What''s the tradeoff of using strict typing in Python?"'
  - '### Day 12: Properties, Classmethods, Staticmethods

    - [ ] Learn: `@property`, `@classmethod`, `@staticmethod` — when to use each

    - [ ] Build: add a `@property` for a computed field (e.g., `word_count`) on `Document`

    - [ ] Interview Q: "When would you use a classmethod instead of `__init__` overloading?"'
  - '### Day 28: Timed Mock Problem — Python-Specific

    - [ ] 45 min: solve a problem requiring generators or decorators

    - [ ] Interview Q: "Show me you understand generators, not just that you can use
    them"


    ### Day 29: Full Mock Interview

    - [ ] Walk through your `vero_ChatBot` project out loud, end-to-end, as if to
    an interviewer

    - [ ] Record yourself if possible — review for filler words and unclear explanations'
pipeline_tag: sentence-similarity
library_name: sentence-transformers
---

# SentenceTransformer based on sentence-transformers/all-MiniLM-L6-v2

This is a [sentence-transformers](https://www.SBERT.net) model finetuned from [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2). It maps sentences & paragraphs to a 384-dimensional dense vector space and can be used for retrieval.

## Model Details

### Model Description
- **Model Type:** Sentence Transformer
- **Base model:** [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) <!-- at revision 1110a243fdf4706b3f48f1d95db1a4f5529b4d41 -->
- **Maximum Sequence Length:** 256 tokens
- **Output Dimensionality:** 384 dimensions
- **Similarity Function:** Cosine Similarity
- **Supported Modality:** Text
<!-- - **Training Dataset:** Unknown -->
<!-- - **Language:** Unknown -->
<!-- - **License:** Unknown -->

### Model Sources

- **Documentation:** [Sentence Transformers Documentation](https://sbert.net)
- **Repository:** [Sentence Transformers on GitHub](https://github.com/huggingface/sentence-transformers)
- **Hugging Face:** [Sentence Transformers on Hugging Face](https://huggingface.co/models?library=sentence-transformers)

### Full Model Architecture

```
SentenceTransformer(
  (0): Transformer({'transformer_task': 'feature-extraction', 'modality_config': {'text': {'method': 'forward', 'method_output_name': 'last_hidden_state'}}, 'module_output_name': 'token_embeddings', 'architecture': 'BertModel'})
  (1): Pooling({'embedding_dimension': 384, 'pooling_mode': 'mean', 'include_prompt': True})
  (2): Normalize({})
)
```

## Usage

### Direct Usage (Sentence Transformers)

First install the Sentence Transformers library:

```bash
pip install -U sentence-transformers
```
Then you can load this model and run inference.
```python
from sentence_transformers import SentenceTransformer

# Download from the 🤗 Hub
model = SentenceTransformer("sentence_transformers_model_id")
# Run inference
sentences = [
    'day 12',
    '### Day 12: Properties, Classmethods, Staticmethods\n- [ ] Learn: `@property`, `@classmethod`, `@staticmethod` — when to use each\n- [ ] Build: add a `@property` for a computed field (e.g., `word_count`) on `Document`\n- [ ] Interview Q: "When would you use a classmethod instead of `__init__` overloading?"',
    '### Day 19: Static Type Checking\n- [ ] Learn: run `mypy` on your typed code, fix the errors it surfaces\n- [ ] Solve: intentionally introduce 3 type bugs, catch them with mypy before running\n- [ ] Interview Q: "What\'s the tradeoff of using strict typing in Python?"',
]
embeddings = model.encode(sentences)
print(embeddings.shape)
# [3, 384]

# Get the similarity scores for the embeddings
similarities = model.similarity(embeddings, embeddings)
print(similarities)
# tensor([[ 1.0000,  0.6468, -0.0635],
#         [ 0.6468,  1.0000,  0.2642],
#         [-0.0635,  0.2642,  1.0000]])
```
<!--
### Direct Usage (Transformers)

<details><summary>Click to see the direct usage in Transformers</summary>

</details>
-->

<!--
### Downstream Usage (Sentence Transformers)

You can finetune this model on your own dataset.

<details><summary>Click to expand</summary>

</details>
-->

<!--
### Out-of-Scope Use

*List how the model may foreseeably be misused and address what users ought not to do with the model.*
-->

<!--
## Bias, Risks and Limitations

*What are the known or foreseeable issues stemming from this model? You could also flag here known failure cases or weaknesses of the model.*
-->

<!--
### Recommendations

*What are recommendations with respect to the foreseeable issues? For example, filtering explicit content.*
-->

## Training Details

### Training Dataset

#### Unnamed Dataset

* Size: 144 training samples
* Columns: <code>anchor</code>, <code>positive</code>, and <code>negative</code>
* Approximate statistics based on the first 100 samples:
  |          | anchor                                                                            | positive                                                                             | negative                                                                            |
  |:---------|:----------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------|
  | type     | string                                                                            | string                                                                               | string                                                                              |
  | modality | text                                                                              | text                                                                                 | text                                                                                |
  | details  | <ul><li>min: 4 tokens</li><li>mean: 10.45 tokens</li><li>max: 19 tokens</li></ul> | <ul><li>min: 50 tokens</li><li>mean: 104.11 tokens</li><li>max: 172 tokens</li></ul> | <ul><li>min: 50 tokens</li><li>mean: 95.53 tokens</li><li>max: 172 tokens</li></ul> |
* Samples:
  | anchor                                 | positive                                                                                                                                                                                                                                                                                                                                                                                 | negative                                                                                                                                                                                                                                                                                                              |
  |:---------------------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
  | <code>day 11</code>                    | <code>### Day 11: Decorators From Scratch<br>- [ ] Learn: functions as first-class objects, closures → decorators<br>- [ ] Build: a `@timing` decorator and a `@retry(times=3)` decorator (parametrized)<br>- [ ] Interview Q: "Walk me through what happens when Python applies a decorator."</code>                                                                                    | <code>### Day 19: Static Type Checking<br>- [ ] Learn: run `mypy` on your typed code, fix the errors it surfaces<br>- [ ] Solve: intentionally introduce 3 type bugs, catch them with mypy before running<br>- [ ] Interview Q: "What's the tradeoff of using strict typing in Python?"</code>                        |
  | <code>day 15</code>                    | <code>---<br><br>## WEEK 3 — Concurrency, Typing, Packaging<br><br>### Day 15: The GIL, Threading vs Multiprocessing<br>- [ ] Learn: what the GIL is, when threading helps (I/O-bound) vs multiprocessing (CPU-bound)<br>- [ ] Compare: how this differs from JS's single-threaded event loop<br>- [ ] Interview Q: "Why doesn't threading speed up CPU-bound Python code?"</code>       | <code>### Day 14: Build & Test a Real Tool<br>- [ ] Build a log-parser CLI tool using everything from Week 2<br>- [ ] Write a full pytest suite for it (aim for meaningful coverage, not 100%)<br>- [ ] Add Week 2 concepts to your interview doc<br><br>---<br><br>## WEEK 3 — Concurrency, Typing, Packaging</code> |
  | <code>what did I learn on day 4</code> | <code>### Day 4: `*args`, `**kwargs`, Unpacking<br>- [ ] Learn: positional/keyword unpacking, `*`, `**` in function defs and calls<br>- [ ] Solve: write a function that logs any function's args/kwargs generically<br>- [ ] Build: a flexible config-merging function using `**kwargs`<br>- [ ] Interview Q: "How would you write a function that accepts unlimited arguments?"</code> | <code>### Day 19: Static Type Checking<br>- [ ] Learn: run `mypy` on your typed code, fix the errors it surfaces<br>- [ ] Solve: intentionally introduce 3 type bugs, catch them with mypy before running<br>- [ ] Interview Q: "What's the tradeoff of using strict typing in Python?"</code>                        |
* Loss: [<code>MultipleNegativesRankingLoss</code>](https://sbert.net/docs/package_reference/sentence_transformer/losses.html#multiplenegativesrankingloss) with these parameters:
  ```json
  {
      "scale": 20.0,
      "similarity_fct": "cos_sim",
      "gather_across_devices": false,
      "directions": [
          "query_to_doc"
      ],
      "partition_mode": "joint",
      "hardness_mode": null,
      "hardness_strength": 0.0
  }
  ```

### Training Hyperparameters
#### Non-Default Hyperparameters

- `per_device_train_batch_size`: 16
- `warmup_steps`: 0.1

#### All Hyperparameters
<details><summary>Click to expand</summary>

- `per_device_train_batch_size`: 16
- `num_train_epochs`: 3
- `max_steps`: -1
- `learning_rate`: 5e-05
- `lr_scheduler_type`: linear
- `lr_scheduler_kwargs`: None
- `warmup_steps`: 0.1
- `optim`: adamw_torch_fused
- `optim_args`: None
- `weight_decay`: 0.0
- `adam_beta1`: 0.9
- `adam_beta2`: 0.999
- `adam_epsilon`: 1e-08
- `optim_target_modules`: None
- `gradient_accumulation_steps`: 1
- `average_tokens_across_devices`: True
- `max_grad_norm`: 1.0
- `label_smoothing_factor`: 0.0
- `bf16`: False
- `fp16`: False
- `bf16_full_eval`: False
- `fp16_full_eval`: False
- `tf32`: None
- `gradient_checkpointing`: False
- `gradient_checkpointing_kwargs`: None
- `torch_compile`: False
- `torch_compile_backend`: None
- `torch_compile_mode`: None
- `use_liger_kernel`: False
- `liger_kernel_config`: None
- `use_cache`: False
- `neftune_noise_alpha`: None
- `torch_empty_cache_steps`: None
- `auto_find_batch_size`: False
- `log_on_each_node`: True
- `logging_nan_inf_filter`: True
- `include_num_input_tokens_seen`: no
- `log_level`: passive
- `log_level_replica`: warning
- `disable_tqdm`: False
- `project`: huggingface
- `trackio_space_id`: None
- `trackio_bucket_id`: None
- `trackio_static_space_id`: None
- `per_device_eval_batch_size`: 8
- `prediction_loss_only`: True
- `eval_on_start`: False
- `eval_do_concat_batches`: True
- `eval_use_gather_object`: False
- `eval_accumulation_steps`: None
- `include_for_metrics`: []
- `batch_eval_metrics`: False
- `save_only_model`: False
- `save_on_each_node`: False
- `enable_jit_checkpoint`: False
- `push_to_hub`: False
- `hub_private_repo`: None
- `hub_model_id`: None
- `hub_strategy`: every_save
- `hub_always_push`: False
- `hub_revision`: None
- `load_best_model_at_end`: False
- `ignore_data_skip`: False
- `restore_callback_states_from_checkpoint`: False
- `full_determinism`: False
- `seed`: 42
- `data_seed`: None
- `use_cpu`: False
- `accelerator_config`: {'split_batches': False, 'dispatch_batches': None, 'even_batches': True, 'use_seedable_sampler': True, 'non_blocking': False, 'gradient_accumulation_kwargs': None}
- `parallelism_config`: None
- `dataloader_drop_last`: False
- `dataloader_num_workers`: 0
- `dataloader_pin_memory`: True
- `dataloader_persistent_workers`: False
- `dataloader_prefetch_factor`: None
- `remove_unused_columns`: True
- `label_names`: None
- `train_sampling_strategy`: random
- `length_column_name`: length
- `ddp_find_unused_parameters`: None
- `ddp_bucket_cap_mb`: None
- `ddp_broadcast_buffers`: False
- `ddp_static_graph`: None
- `ddp_backend`: None
- `ddp_timeout`: 1800
- `fsdp`: None
- `fsdp_config`: None
- `deepspeed`: None
- `debug`: []
- `skip_memory_metrics`: True
- `do_predict`: False
- `resume_from_checkpoint`: None
- `warmup_ratio`: None
- `local_rank`: -1
- `prompts`: None
- `batch_sampler`: batch_sampler
- `multi_dataset_batch_sampler`: proportional
- `router_mapping`: {}
- `learning_rate_mapping`: {}

</details>

### Training Logs
| Epoch  | Step | Training Loss |
|:------:|:----:|:-------------:|
| 1.1111 | 10   | 3.1814        |
| 2.2222 | 20   | 1.8649        |


### Training Time
- **Training**: 11.3 seconds

### Framework Versions
- Python: 3.14.6
- Sentence Transformers: 5.6.0
- Transformers: 5.13.0
- PyTorch: 2.13.0
- Accelerate: 1.14.0
- Datasets: 5.0.0
- Tokenizers: 0.22.2

## Citation

### BibTeX

#### Sentence Transformers
```bibtex
@inproceedings{reimers-2019-sentence-bert,
    title = "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks",
    author = "Reimers, Nils and Gurevych, Iryna",
    booktitle = "Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing",
    month = "11",
    year = "2019",
    publisher = "Association for Computational Linguistics",
    url = "https://arxiv.org/abs/1908.10084",
}
```

#### MultipleNegativesRankingLoss
```bibtex
@misc{oord2019representationlearningcontrastivepredictive,
      title={Representation Learning with Contrastive Predictive Coding},
      author={Aaron van den Oord and Yazhe Li and Oriol Vinyals},
      year={2019},
      eprint={1807.03748},
      archivePrefix={arXiv},
      primaryClass={cs.LG},
      url={https://arxiv.org/abs/1807.03748},
}
```

<!--
## Glossary

*Clearly define terms in order to be accessible across audiences.*
-->

<!--
## Model Card Authors

*Lists the people who create the model card, providing recognition and accountability for the detailed work that goes into its construction.*
-->

<!--
## Model Card Contact

*Provides a way for people who have updates to the Model Card, suggestions, or questions, to contact the Model Card authors.*
-->