# DistilBERT Issue Classifier

**Base model:** distilbert-base-uncased  
**Task:** 4-class GitHub issue classification (bug / feature / docs / question)  
**Training data:** home-assistant/core + home-assistant.io (closed issues)

## Results (test split)

| Metric | Value |
|--------|-------|
| Accuracy | 0.6259 |
| Macro F1 | 0.6312 |
| Bug F1 | 0.6078 |
| Feature F1 | 0.5665 |
| Docs F1 | 0.9474 |
| Question F1 | 0.403 |

## Training Config

- Epochs: 8
- Batch size: 32
- Learning rate: 2e-05
- Max token length: 256
- Class weights: balanced
- Best checkpoint: epoch 6
