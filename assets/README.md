# Assets

`ai-presence-alarm.wav` e um alarme original e opcional, sintetizado pelo
script rastreavel `scripts/generate_alarm_asset.py`. Ele nao contem gravacao ou
amostra de terceiros, nao e carregado automaticamente e nao faz parte do
wheel.

Proveniencia:

- autor do script e da composicao parametrica: Josue Amaral;
- formato: PCM WAV mono, 16 bits, 44.100 Hz;
- sintese: onda quadrada por aritmetica inteira, sem dependencia de `libm`;
- padrao: tres ciclos de 880 Hz por 180 ms, 80 ms de silencio, 660 Hz por
  180 ms e 200 ms de silencio;
- amplitude de sintese: 10.485 na faixa PCM de 16 bits (aproximadamente 32%);
- licenca: Apache-2.0, conforme o arquivo `LICENSE` na raiz;
- SHA-256: `5c175336ed360d80e37d06ad219e3ce6d28f564279b5a21d5af1a229e906ec29`.

Reproducao:

```bash
python scripts/generate_alarm_asset.py \
  --output assets/ai-presence-alarm.wav
sha256sum assets/ai-presence-alarm.wav
```

Uma configuracao pode referencia-lo por caminho absoluto:

```env
RED_NOTIFICATION_MODE=alarm
RED_ALERT_COMMAND=paplay /caminho/para/ai-presence-monitor/assets/ai-presence-alarm.wav
```

O usuario deve configurar um caminho absoluto. A instalacao e o upgrade nao
alteram o `.env` e nunca habilitam nem reproduzem o alarme automaticamente.
