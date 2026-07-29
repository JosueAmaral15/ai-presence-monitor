# Assets

`alarm-four2.mp3` e um arquivo local opcional para testes de alerta sonoro. Ele
nao e carregado automaticamente e nao faz parte do wheel.

Uma configuracao pode referencia-lo por caminho absoluto:

```env
RED_NOTIFICATION_MODE=alarm
RED_ALERT_COMMAND=paplay /caminho/para/ai-presence-monitor/assets/alarm-four2.mp3
```

O nome e a localizacao foram preservados para nao quebrar configuracoes locais
existentes.
