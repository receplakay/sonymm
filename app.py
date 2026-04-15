import streamlit as st
import os
import json
import re
import streamlit.components.v1 as components

try:
    import google.generativeai as genai
    import PyPDF2
except ImportError:
    st.error("Lütfen terminalde 'pip3 install google-generativeai PyPDF2' komutunu çalıştırınız.")
    st.stop()

# --- PAGE CONFIG ---
st.set_page_config(page_title="Mevzuat & YMM AI", page_icon="⚖️", layout="wide")

# --- SESSION STATE INITIALIZATION ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "total_tokens" not in st.session_state:
    st.session_state.total_tokens = 0
if "total_cost" not in st.session_state:
    st.session_state.total_cost = 0.0

# --- PRICES (Paid Tier 1 Estimated Rates) ---
PRICES = {
    "gemini-1.5-flash": {"input": 0.075 / 1000000, "output": 0.30 / 1000000},
    "gemini-1.5-pro": {"input": 1.25 / 1000000, "output": 5.00 / 1000000}
}

# --- CUSTOM CSS ---
st.markdown("""
<style>
/* Print Styles */
@media print {
    div[data-testid="stSidebar"], .stButton, .stChatInput, header, .stDownloadButton { display: none !important; }
    .main .block-container { padding-top: 0 !important; }
}

/* Sidebar Cost Info */
.cost-card {
    background-color: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    padding: 15px;
    margin-bottom: 20px;
}
.cost-value {
    font-size: 1.5em;
    font-weight: 800;
    color: #0f172a;
    display: block;
}
.cost-label {
    font-size: 0.8em;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* Meta Info */
.meta-info { font-size: 0.75em; color: #94a3b8; text-align: right; margin-top: -10px; margin-bottom: 15px; font-style: italic; }

.flashcard { background-color: #ffffff; border: 2px solid #e2e8f0; border-radius: 12px; padding: 16px; margin: 12px 0; border-left: 5px solid #2563eb; }
.flashcard-q { font-size: 1.05em; font-weight: 700; color: #0f172a; margin-bottom: 8px; }
.flashcard-a { color: #475569; border-top: 1px dashed #cbd5e1; padding-top: 10px; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
@st.cache_data(show_spinner=False)
def extract_pdf_text(filepath):
    text = ""
    try:
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        return f"[PDF Okuma Hatası: {str(e)}]"
    return text

def update_cost(model_id, in_tokens, out_tokens):
    # Model ID normalizasyonu
    clean_id = "gemini-1.5-flash" if "flash" in model_id.lower() else "gemini-1.5-pro"
    p = PRICES[clean_id]
    cost = (in_tokens * p["input"]) + (out_tokens * p["output"])
    st.session_state.total_tokens += (in_tokens + out_tokens)
    st.session_state.total_cost += cost
    return cost

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚖️ Kontrol Paneli")
    
    # Canlı Maliyet Göstergesi
    st.markdown(f"""
    <div class="cost-card">
        <span class="cost-label">Oturum Harcaması</span>
        <span class="cost-value">${st.session_state.total_cost:.5f}</span>
        <hr style="margin: 10px 0; border: none; border-top: 1px solid #cbd5e1;">
        <span class="cost-label">Toplam Token</span>
        <span class="cost-value" style="font-size: 1em;">{st.session_state.total_tokens:,}</span>
    </div>
    """, unsafe_allow_html=True)

    api_key = st.text_input("Gemini API Anahtarı", type="password")
    if api_key: genai.configure(api_key=api_key)

    selected_model_name = st.selectbox(
        "🧠 Model Seçimi:",
        options=["Gemini 1.5 Flash (Hızlı)", "Gemini 1.5 Pro (Derin)"],
        index=0
    )
    model_id_map = {"Gemini 1.5 Flash (Hızlı)": "gemini-1.5-flash", "Gemini 1.5 Pro (Derin)": "gemini-1.5-pro"}
    target_model_id = model_id_map[selected_model_name]

    st.divider()
    st.title("📚 Knowledge")
    
    DERS_KODLARI = {
        "01": "İleri Düzey Finansal Muhasebe",
        "02": "Finansal Yönetim",
        "03": "Yönetim Muhasebesi",
        "04": "Denetim, Tasdik ve Meslek Hukuku",
        "05": "Revizyon",
        "06": "Vergi Tekniği",
        "07": "Gelir Üzerinden Alınan Vergiler",
        "08": "Harcama ve Servet Üz. Alınan Vergiler",
        "09": "Dış Ticaret ve Kambiyo Mevzuatı",
        "10": "Sermaye Piyasası Mevzuatı"
    }

    base_dir = os.path.dirname(os.path.abspath(__file__))
    tesmer_dir = os.path.join(base_dir, "TESMER_Sorular")
    gib_dir = os.path.join(base_dir, "GIB_Ozelgeler")
    
    raw_files = []
    processed = set()
    def scan(p):
        if os.path.exists(p) and os.path.isdir(p):
            for f in os.listdir(p):
                if f.endswith(".pdf") and f not in processed:
                    processed.add(f)
                    match = re.search(r'ymm_(\d{4})_(\d)_(\d{2})', f)
                    if match:
                        yil = int(match.group(1))
                        donem = int(match.group(2))
                        ders = match.group(3)
                        raw_files.append((yil, donem, ders, f, os.path.join(p, f)))
                    else:
                        raw_files.append((9999, 9, "99", f, os.path.join(p, f)))

    scan(tesmer_dir)
    scan(gib_dir)
    scan(base_dir)
    
    raw_files.sort(key=lambda x: (x[0], x[1], x[2]))

    all_files = {}
    for yil, donem, ders, f, fpath in raw_files:
        if yil != 9999:
            ders_adi = DERS_KODLARI.get(ders, f"Ders Kod {ders}")
            label = f"[{yil} / {donem}. Dönem] {ders_adi}"
            all_files[label] = fpath
        else:
            all_files[f] = fpath
    
    selected_files = st.multiselect("Dökümanlar:", options=list(all_files.keys()))

    if st.button("🗑️ Sohbeti Temizle"):
        st.session_state.messages = []
        st.rerun()

# --- MAIN UI ---
st.title("⚖️ Kıdemli YMM Ajanı")
st.caption("Eğitim, Denetim ve Mevzuat Analiz Raporlama Ekranı")

# Mesajları Render Et
for idx, message in enumerate(st.session_state.messages):
    msg_type = message.get("type", "text")
    with st.chat_message(message["role"]):
        if msg_type == "text":
            st.markdown(message["content"], unsafe_allow_html=True)
            if "meta" in message: st.markdown(f"<div class='meta-info'>{message['meta']}</div>", unsafe_allow_html=True)
        elif msg_type == "quiz":
            quiz_data = message["content"]
            quiz_id = f"quiz_{idx}"
            if f"submitted_{quiz_id}" not in st.session_state: st.session_state[f"submitted_{quiz_id}"] = False
            with st.form(key=f"form_{quiz_id}", border=True):
                st.subheader("📝 YMM Deneme Testi")
                for q_idx, q in enumerate(quiz_data.get("questions", [])):
                    st.markdown(f"**Soru {q_idx + 1}:** {q['question']}")
                    st.radio("Şıklar:", q["options"], key=f"radio_{quiz_id}_{q_idx}", index=None, disabled=st.session_state[f"submitted_{quiz_id}"])
                    st.divider()
                if st.form_submit_button("Testi Tamamla", disabled=st.session_state[f"submitted_{quiz_id}"], type="primary"):
                    st.session_state[f"submitted_{quiz_id}"] = True
                    st.rerun()
            if st.session_state[f"submitted_{quiz_id}"]:
                with st.expander("📊 SONUÇLAR", expanded=True):
                    for q_idx, q in enumerate(quiz_data.get("questions", [])):
                        correct = q["options"][q["correct_index"]]
                        selected = st.session_state.get(f"radio_{quiz_id}_{q_idx}")
                        if selected == correct: st.success(f"✅ Soru {q_idx+1}: Doğru")
                        else: st.error(f"❌ Soru {q_idx+1}: Yanlış. Doğru: {correct}\n\n💡 {q['explanation']}")
            if "meta" in message: st.markdown(f"<div class='meta-info'>{message['meta']}</div>", unsafe_allow_html=True)

# Study Modes
c1, c2, c3 = st.columns(3)
special_action = None
if c1.button("📝 Test Üret"): special_action = "Test"
elif c2.button("🃏 Flashcard"): special_action = "Flashcard"
elif c3.button("📚 YMM Sınav Özeti"): special_action = "Ozet"

prompt = st.chat_input("Vergi sorunuzu yazın...")
if special_action == "Test": prompt = "[Test Üret JSON]"
elif special_action == "Flashcard": prompt = "[Flashcard Üret]"
elif special_action == "Ozet": prompt = "[Özet Üret]"

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt, "type": "text"})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        if not api_key: st.error("Lütfen API anahtarını girin.")
        else:
            try:
                # Context Okuma
                context_txt = ""
                for fname in selected_files:
                    with st.spinner(f"{fname} okunuyor..."):
                        context_txt += f"\n--- KAYNAK: {fname} ---\n{extract_pdf_text(all_files[fname])}\n"
                
                try:
                    available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    if f"models/{target_model_id}" not in available:
                        target_model_id = available[0].replace("models/", "") if available else "gemini-pro"
                except:
                    pass

                model = genai.GenerativeModel(target_model_id)
                system_prompt = f"""Sen YMM'sın. Sorulacak soruları yanıtlarken şu KATI kurala uy:
1. Metin içinde kanun veya tebliğe atıf yaptığında ASLA cümlenin içine kanun metni açıklamasını, özetini veya [FOOTNOTE] gibi ifadeler sıkıştırma. SADECE [1], [2] şeklinde referans numarası ver ve cümlene devam et (Örn: GVK Madde 11'e göre [1]...).
2. Cevabını tamamen bitirdikten sonra, EN ALTA '---' işaretiyle yatay bir çizgi çek ve "📚 İlgili Mevzuat Maddeleri" başlığı at.
3. Metin içinde verdiğin [1], [2] nolu referansların karşılığı olan mevzuat bölümlerinin KANUNDAKİ BİREBİR TAM METİNLERİNİ bu başlığın altına listele. Asla özet veya yorum katma.

Kaynaklar:
{context_txt}"""
                
                # Token Sayımı (Input)
                try:
                    in_tokens = model.count_tokens(system_prompt + prompt).total_tokens
                except:
                    in_tokens = 0
                
                model_kwargs = {}
                if special_action == "Test": model_kwargs["generation_config"] = {"response_mime_type": "application/json"}
                
                with st.spinner("Yapay zeka analiz ediyor..."):
                    response = model.generate_content(system_prompt + prompt, **model_kwargs)
                    out_tokens = response.usage_metadata.candidates_token_count if hasattr(response, "usage_metadata") else 0
                
                raw_resp = response.text
                query_cost = update_cost(target_model_id, in_tokens, out_tokens)
                meta_str = f"Maliyet: ${query_cost:.5f} | Toplam: {in_tokens+out_tokens} token | Model: {target_model_id}"
                
                if special_action == "Test":
                    try:
                        cleaned = raw_resp.strip()
                        if "```json" in cleaned: cleaned = cleaned.split("```json")[1].split("```")[0]
                        quiz_data = json.loads(cleaned)
                        st.session_state.messages.append({"role": "assistant", "type": "quiz", "content": quiz_data, "meta": meta_str})
                    except: st.error("Hatalı JSON formatı.")
                else:
                    st.markdown(raw_resp, unsafe_allow_html=True)
                    st.markdown(f"<div class='meta-info'>{meta_str}</div>", unsafe_allow_html=True)
                    st.session_state.messages.append({"role": "assistant", "content": raw_resp, "type": "text", "meta": meta_str})
                
                st.rerun()
            except Exception as e: st.error(f"İşlem Hatası: {e}")

# Export
st.write(""); st.divider()
ec1, ec2, ec3 = st.columns([2, 2, 4])
with ec1:
    if st.button("🖨️ Sayfayı PDF Olarak Kaydet"): components.html("<script>parent.window.print();</script>", height=0)
with ec2:
    txt_out = ""
    for m in st.session_state.messages: 
        if m["type"] == "text":
            txt_out += f"{m['role'].upper()}: {m['content']}\n\n"
    st.download_button("💾 TXT İndir", txt_out, "rapor.txt")
