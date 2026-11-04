# Archivo histórico de capturas — no usar como evaluación ni ajuste v2

Son copias verificadas de objetos Git. No se movieron, renombraron ni recodificaron
las fotografías de evaluación/ajuste. Los CSV y las procedencias originales
conservan sus bytes. El atributo local -text evita conversiones de fin de línea.

| Snapshot | Commit fuente | JPEG | S1/S2/S3/S4/S5/S6 | Despejado/obstáculo |
|---|---|---:|---|---|
| [protocolo_v1](protocolo_v1/) | 021550eafbe1cc7d32f9474ed47f9d1dec53724a | 84 | 18/17/13/12/12/12 | 26/58 |
| [seleccion_78_pre_recaptura](seleccion_78_pre_recaptura/) | bd1ff9efadf38a07d1040be0d1f1b309f820e837 | 78 | 12/17/13/12/12/12 | 20/58 |

Los 84 se introdujeron en e47b98b9dab82043eb86d016627077e014491b6e y se conservaron
en 021550e. La selección de 78 se aplicó en 129f6607c1727dd3754d4a56381eefdfa15ccb95;
bd1ff9e solo corrigió documentación posterior. Se retiraron ocho S1 y recuperaron
dos S1 originales; los 76 registros compartidos conservan todos sus campos.

| CSV | SHA-256 |
|---|---|
| Histórico 84 | 07fff3a7dcb727d4c4f12ced5799124708af03c415a24e69f6ca6e3a1842f511 |
| Vigente 78 | e4d124463349fdd050435b256f1b2b605e776f871379e964d89781f560cf5853 |

Cada carpeta contiene sus JPEG con rutas S1/...S6/, capturas.csv, la copia
procedencia_original.json, archivo.json con commit y método, y HASHES.sha256
para todos los archivos salvo el propio manifiesto. Los tiempos/IDs son de
captura; archivo_creado_utc identifica únicamente cuándo se hizo esta copia.

Los duplicados entre ambos snapshots son deliberados para conservar las dos
selecciones completas; no son capturas nuevas y no deben sumarse al conjunto
activo. Los siete cuadros de ajuste siguen en su ubicación y no forman parte
de estas 84/78 fotografías archivadas. El validador activo examina evaluación
y ajuste, no estas carpetas hermanas.

[Protocolo de recaptura y pendientes del PM](../../docs/protocolo_recaptura_persona_issue57.md).
