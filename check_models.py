from transformers import AutoConfig

for name in ['gpt2', 'sshleifer/tiny-gpt2']:
    cfg = AutoConfig.from_pretrained(name)
    hidden = cfg.n_embd if hasattr(cfg, 'n_embd') else cfg.hidden_size
    layers = cfg.n_layer if hasattr(cfg, 'n_layer') else cfg.num_hidden_layers
    print(f'{name}: hidden={hidden}, layers={layers}, vocab={cfg.vocab_size}')
