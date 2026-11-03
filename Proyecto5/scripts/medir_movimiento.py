"""Registro manual de movimiento. No contiene transporte ni comandos para motores."""

from __future__ import annotations

import argparse
from pathlib import Path

from mediciones_core import OUTPUT, export_report, positive, repetitions, seconds, statistics_of

BASELINE = {
    "fuente": "Operador; mediciones manuales iniciales, sin registros crudos proporcionados",
    "lineal_m_s": 0.545,
    "lineal_km_h": 1.962,
    "giro_derecha": {"angulo_aproximado_grados": 90, "tiempo_observado_s": 0.35},
    "giro_izquierda": {"angulo_aproximado_grados": 90, "tiempo_observado_s": 0.35},
    "angular_estimada_grados_s": 90 / 0.35,
}


def calculate_trial(kind, observed_time, distance=None, angle=None):
    observed_time = positive(observed_time)
    if kind == "avance":
        speed = positive(distance) / observed_time
        return {"velocidad_m_s": speed, "velocidad_km_h": speed * 3.6}
    if kind not in ("izquierda", "derecha"):
        raise ValueError("Tipo de prueba desconocido")
    return {"velocidad_angular_grados_s": positive(angle) / observed_time}


def summarize(trials):
    result = {}
    for kind in ("avance", "izquierda", "derecha"):
        group = [trial for trial in trials if trial["tipo"] == kind]
        if not group:
            continue
        fields = (
            ("velocidad_m_s", "velocidad_km_h")
            if kind == "avance"
            else ("velocidad_angular_grados_s",)
        )
        summary = {field: statistics_of([trial[field] for trial in group]) for field in fields}
        field = fields[0]
        reference = (
            BASELINE["lineal_m_s"] if kind == "avance" else BASELINE["angular_estimada_grados_s"]
        )
        summary["diferencia_media_vs_referencia"] = summary[field]["media"] - reference
        result[kind] = summary
    return result


def ask_number(prompt, optional=False, maximum=None):
    while True:
        raw = input(prompt).strip()
        if not raw and optional:
            return None
        try:
            value = positive(raw.replace(",", "."))
            if maximum is not None and value > maximum:
                raise ValueError(f"Máximo permitido: {maximum:g} s")
            return value
        except ValueError as exc:
            print(f"Entrada inválida: {exc}")


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--tipo", choices=("avance", "izquierda", "derecha", "todos"), default="todos"
    )
    result.add_argument("--repeticiones", type=repetitions, default=3)
    result.add_argument(
        "--nivel", help="Texto exacto de la consigna web; no se interpreta como m/s"
    )
    result.add_argument("--condiciones", default="No registradas")
    result.add_argument("--duracion-solicitada", type=seconds, help="Consigna manual en s, <=2")
    result.add_argument("--salida", type=Path, default=OUTPUT)
    result.add_argument(
        "--dry-run", action="store_true", help="Registro sin actuar; es el modo predeterminado"
    )
    result.add_argument(
        "--modo-real", action="store_true", help="No disponible: protocolo/STOP sin verificar"
    )
    return result


def main(argv=None):
    argument_parser = parser()
    args = argument_parser.parse_args(argv)
    if args.modo_real:
        argument_parser.error(
            "Modo real bloqueado: falta firmware, STOP y parada independiente comprobada. "
            "No se envió ningún comando."
        )
    if args.duracion_solicitada is not None and args.duracion_solicitada > 2:
        argument_parser.error("--duracion-solicitada no debe superar 2 s")
    print("DRY-RUN / REGISTRO MANUAL: no se conecta al carrito ni mueve motores.")
    print("Introducir mediciones observadas; el tiempo de giro no es el de pulsación.")
    report = {
        "modo": "registro_manual_sin_actuacion",
        "referencia_inicial_operador": BASELINE,
        "condiciones": args.condiciones,
        "pruebas": [],
        "completa": False,
    }
    interrupted = False
    try:
        level = args.nivel or input("Consigna de velocidad utilizada en la web: ").strip()
        if not level:
            raise ValueError("Registrar la consigna, o indicar explícitamente desconocida")
        kinds = ("avance", "izquierda", "derecha") if args.tipo == "todos" else (args.tipo,)
        for kind in kinds:
            for number in range(1, args.repeticiones + 1):
                print(f"\n{kind}, repetición {number}/{args.repeticiones}; solo registro de datos.")
                requested = args.duracion_solicitada
                if requested is None:
                    requested = ask_number(
                        "Duración SOLICITADA del comando (s; Enter si desconocida, <=2): ",
                        optional=True,
                        maximum=2,
                    )
                actual = ask_number(
                    "Duración REAL del comando (s; Enter si no medida): ", optional=True
                )
                observed = ask_number("Tiempo OBSERVADO del recorrido/giro (s): ")
                distance = ask_number("Distancia medida (m): ") if kind == "avance" else None
                angle = (
                    ask_number("Ángulo REAL observado, magnitud en grados: ")
                    if kind != "avance"
                    else None
                )
                trial = {
                    "tipo": kind,
                    "repeticion": number,
                    "consigna_web": level,
                    "duracion_solicitada_comando_s": requested,
                    "duracion_real_comando_s": actual,
                    "tiempo_observado_s": observed,
                    "distancia_m": distance,
                    "angulo_observado_grados": angle,
                    **calculate_trial(kind, observed, distance, angle),
                }
                report["pruebas"].append(trial)
                print(trial)
        report["completa"] = True
    except (KeyboardInterrupt, EOFError):
        interrupted = True
        print(
            "\nRegistro interrumpido; se conservan las pruebas completas. No se enviaron comandos."
        )
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1
    finally:
        if report["pruebas"]:
            report["resumen"] = summarize(report["pruebas"])
            print("Resumen:", report["resumen"])
            print("Informe:", export_report(report, args.salida, "movimiento"))
    return 130 if interrupted else 0


if __name__ == "__main__":
    raise SystemExit(main())
