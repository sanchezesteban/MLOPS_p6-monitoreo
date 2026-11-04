# Evidencia del runner de casos (P5-13)

Corrida del **4 nov 2026** con `p5.casos` contra la política de P5-10 (#73), el
adaptador virtual de P5-11 (#74) y el watchdog de P5-12 (#76), ya mergeados en `main`.
Los casos reales usan los eventos de P5-14 (`datos/eventos/S1.jsonl` … `S6.jsonl`, modo
`cortes_sesion`); los sintéticos no usan detector ni datos reales.

```bash
cd Proyecto5
PYTHONPATH=src python -m p5.casos \
    --casos casos \
    --config config/politica.yaml \
    --control-config config/watchdog.yaml \
    --salida resultados/casos
```

Resultado:

```text
C01  pass   Via libre
C02  fail   Obstaculo central
C03  fail   Obstaculo solo a la izquierda
C04  pass   Obstaculo solo a la derecha
C05  pass   Varios obstaculos sin zona libre
C06  pass   Deteccion bajo umbral y luego sobre umbral
C07  fail   Libre, obstaculo persistente y desaparicion
C08  pass   Corte de cuadros y cuadro vencido
C09  pass   Error del detector, imagen ilegible y salida no finita
C10  pass   Emergencia, rearme y cierre

Resultado: 7/10 casos pasan (codigo de salida 1)
```

## Fallos y lectura

| Caso | Fallo | Causa |
|---|---|---|
| C02 | `S2_f0011`–`S2_f0013` salen FORWARD con el centro anotado como bloqueado | El detector pierde la persona en esos cuadros; la política no frena lo que no ve. `docs/detector.md` §5. |
| C03 | `S3_f0003` y `S3_f0010` salen FORWARD en cuadros de centro | La anotación de fase 2 marca centro por borde (0.2–1.7 px) en cuatro cuadros de S3; el detector no ve el sujeto en dos de ellos. PR #87. |
| C07 | `S6_f0006` y `S6_f0008` salen FORWARD y hay movimiento entre ellos | En S6 no aparecen `person`/`dog`/`cat` en los cuadros con obstáculo; C7 no se cumple con el detector actual. `docs/detector.md` §5. |

No se ajustaron las expectativas para hacer pasar estos casos: la expectativa sale de la
geometría anotada y el fallo es del detector. C01, C04, C05, C06 y C08–C10 pasan: la
cadena de política, adaptador, watchdog, histéresis y replay de cortes funciona.

## Archivos

- `resumen.json`: resumen de la corrida, hashes de expectativas y referencias a los
  comandos observados. Las rutas de los fallos son relativas a `Proyecto5/`.
- `C01/comandos.jsonl` … `C10/comandos.jsonl`: bitácoras por caso.
- `fallo_inducido.txt`: salida de la corrida sobre una copia de `casos/` con la expectativa
  de `c08_f0004` cambiada a `FORWARD`. El runner sale con código 1.
- `fallo_inducido_resumen.json`: resumen JSON de ese fallo.

## Pendiente

- La fase 2 de P5-06 (#87) ya está en `main`: `datos/anotaciones.json` y
  `datos/manifiesto.csv` cubren las 78 imágenes. Esta corrida usa los `cuadros_S*.csv`
  congelados de P5-15 y no cambia con esa anotación.
- Si el PM decide mejorar el detector o cambiar el estímulo, repetir C01–C10 y actualizar
  esta evidencia. No se cambian las expectativas para ocultar C02/C03/C07.
