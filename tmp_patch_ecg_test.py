from pathlib import Path

p = Path(r'E:\Benjamin_Ruggieri\Kennedy\5T\Catedra Compartida\totem-triaje-preventivo-base\app\modules\ecg\test_router.py')
text = p.read_text(encoding='utf-8')
start = text.index('def test_pantalla_transversal_no_solicita_paciente_sin_contexto')
end = text.index('def test_api_pacientes_devuelve_registros_reales_para_modo_prueba')
new = '''def test_pantalla_transversal_no_solicita_paciente_sin_contexto(ecg_client):
    html_response = ecg_client.get("/api/v1/ecg/circuito/pantalla")

    assert html_response.status_code == 200
    assert html_response.headers["cache-control"] == "no-store"
    assert 'name="tipo_circuito" value="GUARDIA"' in html_response.text
    assert 'name="tipo_circuito" value="COMPLETO"' in html_response.text
    assert 'id="paciente-id-entrada"' not in html_response.text
    assert 'id="crear-episodio" type="button" disabled' in html_response.text
    assert "no define un mecanismo para compartirlo entre pantallas" in html_response.text
    assert 'id="abrir-ecg"' in html_response.text
    assert "Si esta pantalla recibe un `episodio_id` real en la URL" in html_response.text
    assert 'id="episodio-activo"' in html_response.text
    assert 'id="episodio-id"' in html_response.text
    assert 'id="episodio-circuito"' in html_response.text
    assert 'id="episodio-inicio"' in html_response.text

'''

p.write_text(text[:start] + new + text[end:], encoding='utf-8')
print('patched')
