from p6.fuente import SecuenciaFuente


def test_secuencia_respeta_fps_y_orden(tmp_path):
    for i in range(3):
        (tmp_path / f"{i}.jpg").write_bytes(b"x")
    man = tmp_path / "m.csv"
    man.write_text("path,sha256\n" + "".join(f"{i}.jpg,\n" for i in range(3)))
    t = [0.0]
    esperas = []

    def dormir(s):
        esperas.append(round(s, 6))
        t[0] += s

    f = SecuenciaFuente(man, tmp_path, "src", fps=5, dormir=dormir, reloj=lambda: t[0])
    frames = list(f.frames())
    assert [x.frame_id for x in frames] == ["src-f00000", "src-f00001", "src-f00002"]
    assert esperas == [0.2, 0.2]  # 1/5 s entre frames
