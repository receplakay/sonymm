import streamlit as st
import os
import json
import re

try:
    import google.generativeai as genai
    import PyPDF2
except ImportError:
    st.error("Lütfen terminalde 'pip3 install google-generativeai PyPDF2' komutunu çalıştırınız.")
    st.stop()

# --- PAGE CONFIG ---
st.set_page_config(page_title="Mevzuat & YMM AI", page_icon="⚖️", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
<style>
/* Açılır Pencere (Accordion) Tasarımı */
details.citation-popup {
    display: block;
    background-color: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    margin: 10px 0;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    transition: all 0.3s ease;
}
details.citation-popup[open] {
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    border-color: #94a3b8;
}
details.citation-popup summary {
    font-weight: 600;
    color: #1e293b;
    cursor: pointer;
    padding: 10px 14px;
    outline: none;
    list-style: none;
    display: flex;
    align-items: center;
}
details.citation-popup summary::-webkit-details-marker {
    display: none;
}
details.citation-popup summary:hover {
    background-color: #f1f5f9;
    border-radius: 8px;
}
details.citation-popup .popup-content {
    padding: 12px 14px;
    border-top: 1px solid #e2e8f0;
    font-size: 0.95em;
    line-height: 1.5;
    color: #334155;
    background-color: #ffffff;
    border-bottom-left-radius: 8px;
    border-bottom-right-radius: 8px;
    font-family: Consolas, monospace;
}

/* Bilgi Kartı (Flashcard) Tasarımı */
.flashcard {
    background-color: #ffffff;
    border: 2px solid #e2e8f0;
    border-radius: 12px;
    padding: 16px;
    margin: 12px 0;
    box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    border-left: 5px solid #2563eb;
}
.flashcard-q {
    font-size: 1.05em;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 8px;
}
.flashcard-a {
    color: #475569;
    border-top: 1px dashed #cbd5e1;
    padding-top: 10px;
    font-weight: 500;
}

.stChatInput {
    padding-bottom: 20px;
}
</style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTION: READ PDF ---
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

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚖️ Ayarlar ve API")
    api_key = st.text_input("Gemini API Anahtarı", type="password", help="Google AI Studio'dan alabileceğiniz ücretsiz API anahtarı.")
    
    selected_model_name = st.selectbox(
        "🧠 Model Seçimi (Kota Dostu):",
        options=["Gemini 1.5 Flash (Hızlı & Ücretsiz Dostu)", "Gemini 1.5 Pro (Zeki ama Kota Yiyebilir)"],
        index=0,
        help="Flash modeli daha hızlıdır ve ücretsiz kota ile daha çok işlem yapmanıza izin verir. Pro modeli daha karmaşık sorular için daha iyidir."
    )
    
    # Model ismini API formatına çevir
    model_id_map = {
        "Gemini 1.5 Flash (Hızlı & Ücretsiz Dostu)": "gemini-1.5-flash",
        "Gemini 1.5 Pro (Zeki ama Kota Yiyebilir)": "gemini-1.5-pro"
    }
    target_model_id = model_id_map[selected_model_name]

    if api_key:
        genai.configure(api_key=api_key)
        st.success("API Anahtarı aktif!")
    else:
        st.warning("Gerçek cevaplar üretebilmek için API anahtarı gereklidir.")

    st.divider()
    st.title("📚 Knowledge (Bilgi Bankası)")
    st.caption("Ajanın analiz etmesi için aşağıdaki belgeleri seçebilirsiniz:")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    tesmer_dir = os.path.join(base_dir, "TESMER_Sorular")
    gib_dir = os.path.join(base_dir, "GIB_Ozelgeler")

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

    raw_files = []
    processed_filenames = set()
    
    def scan_directory_for_pdfs(folder_path):
        if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
            return
        for f in os.listdir(folder_path):
            if f.endswith('.pdf') and f not in processed_filenames:
                processed_filenames.add(f)
                fpath = os.path.join(folder_path, f)
                match = re.search(r'ymm_(\d{4})_(\d)_(\d{2})', f)
                if match:
                    yil = int(match.group(1))
                    donem = int(match.group(2))
                    ders = match.group(3)
                    raw_files.append((yil, donem, ders, f, fpath))
                else:
                    raw_files.append((9999, 9, "99", f, fpath))

    scan_directory_for_pdfs(tesmer_dir)
    scan_directory_for_pdfs(gib_dir)
    scan_directory_for_pdfs(base_dir)

    raw_files.sort(key=lambda x: (x[0], x[1], x[2]))

    all_files = {}
    for yil, donem, ders, f, fpath in raw_files:
        if yil != 9999:
            ders_adi = DERS_KODLARI.get(ders, f"Ders Kod {ders}")
            label = f"[{yil} / {donem}. Dönem] {ders_adi}"
            all_files[label] = fpath
        else:
            all_files[f] = fpath
    
    selected_files = st.multiselect(
        "💡 Bağlama Eklenecek Dökümanlar:", 
        options=list(all_files.keys()),
        default=[],
        help="Seçilen PDF'lerin içindeki metinler ajanın beynine (Context) aktarılır."
    )

# --- MAIN CHAT INTERFACE ---
st.title("⚖️ Kıdemli YMM Ajanı")
st.caption("NotebookLM Tarzı Asistan: Direkt Kanun metni referansları ve Etkileşimli Testler.")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "type": "text", "content": "Merhaba Meslektaşım! \n\nSol menüden PDF'lerinizi Knowledge sistemine dahil edebilir, vergi soruları sorabilir veya **sayfanın altındaki butonları** kullanarak seçtiğiniz dokümanlardan canlı deneme testleri üretebilirsiniz."}
    ]

# Önceki mesajları ekranda renderla
for idx, message in enumerate(st.session_state.messages):
    msg_type = message.get("type", "text")
    
    with st.chat_message(message["role"]):
        if msg_type == "text":
            st.markdown(message["content"], unsafe_allow_html=True)
            
        elif msg_type == "quiz":
            quiz_data = message["content"]
            quiz_id = f"quiz_{idx}"
            
            if f"submitted_{quiz_id}" not in st.session_state:
                st.session_state[f"submitted_{quiz_id}"] = False

            with st.form(key=f"form_{quiz_id}", border=True):
                st.subheader("📝 YMM Deneme Testi")
                for q_idx, q in enumerate(quiz_data.get("questions", [])):
                    st.markdown(f"**Soru {q_idx + 1}:** {q['question']}")
                    st.radio(
                        "Şıklar:", 
                        q["options"], 
                        key=f"radio_{quiz_id}_{q_idx}", 
                        index=None, 
                        disabled=st.session_state[f"submitted_{quiz_id}"]
                    )
                    st.divider()
                
                submit_label = "Testi Tamamla (Sonuçları Gör)" if not st.session_state[f"submitted_{quiz_id}"] else "Test Tamamlandı ✅"
                submitted = st.form_submit_button(submit_label, disabled=st.session_state[f"submitted_{quiz_id}"], type="primary")
                
                if submitted:
                    st.session_state[f"submitted_{quiz_id}"] = True
                    st.rerun()
                    
            if st.session_state[f"submitted_{quiz_id}"]:
                with st.expander("📊 TIKLA: TEST SONUÇLARI VE AÇIKLAMALAR", expanded=True):
                    for q_idx, q in enumerate(quiz_data.get("questions", [])):
                        correct_idx = q["correct_index"]
                        if correct_idx < len(q["options"]):
                            correct_option = q["options"][correct_idx]
                        else:
                            correct_option = "Bilinmiyor"
                            
                        selected = st.session_state.get(f"radio_{quiz_id}_{q_idx}")
                        
                        if selected == correct_option:
                            st.success(f"✅ **Soru {q_idx + 1}:** Doğru Cevap!")
                        elif selected is None:
                            st.warning(f"⚠️ **Soru {q_idx + 1}:** Boş bırakıldı! (Doğru Cevabın Şuydu: {correct_option})")
                            st.info(f"💡 **Kanuni Dayanak / Açıklama:** {q['explanation']}")
                        else:
                            st.error(f"❌ **Soru {q_idx + 1}:** Yanlış! Senin seçimin: {selected} | Doğru Cevap: {correct_option}")
                            st.info(f"💡 **Kanuni Dayanak / Açıklama:** {q['explanation']}")

st.write("")
st.caption("🎓 **Çalışma Modları:** Seçtiğiniz PDF dokümanlardan otomatik çalışma asistanı içerikleri ürettirin!")
c1, c2, c3 = st.columns(3)
special_action = None

if c1.button("📝 Etkileşimli Test Üret", use_container_width=True):
    special_action = "Test"
if c2.button("🃏 Bilgi Kartı (Flashcard)", use_container_width=True):
    special_action = "Flashcard"
if c3.button("📚 Kapsamlı YMM Sınav Özeti", use_container_width=True):
    special_action = "Ozet"

prompt = st.chat_input("Vergi sorunuzu yazın...")

if special_action:
    if special_action == "Test":
        prompt = """[Yapay Zeka Talimatı: Sisteme Eklediğim Bilgi Bankası dokümanlarını analiz et ve içindeki konulardaki en kilit, sınava yönelik detaylardan oluşan YMM seviyesi 5 soruluk deneme testi üret. 

JSON FORMAT KURALI: 
{
  "questions": [
    {
      "question": "Soru...",
      "options": ["A", "B", "C", "D", "E"],
      "correct_index": 0,
      "explanation": "..."
    }
  ]
}]"""
    elif special_action == "Flashcard":
        prompt = "[Seçili dokümanlardan 5 adet görsel Bilgi Kartı oluştur.]"
    elif special_action == "Ozet":
        prompt = "[Seçili dokümanlardaki sınav tuzaklarını ve revizyon noktalarını özetle.]"

if prompt:
    st.session_state.messages.append({"role": "user", "type": "text", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        if not api_key:
            message_placeholder.error("⚠️ Lütfen API anahtarı giriniz.")
        else:
            try:
                context_text = ""
                if selected_files:
                    with st.spinner("Okunuyor..."):
                        for fname in selected_files:
                            context_text += f"\n\n--- DÖKÜMAN: {fname} ---\n{extract_pdf_text(all_files[fname])}\n"

                # Kullanıcının seçtiği modeli kullan (Eğer desteklenmiyorsa fallback yap)
                try:
                    available_names = [m.name for m in genai.list_models()]
                    if f"models/{target_model_id}" not in available_names:
                        # Fallback: Eğer seçilen model yoksa listedeki ilk uyumlu modeli bul
                        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                        target_model_id = available[0].replace("models/", "") if available else "gemini-1.5-flash"
                except:
                    pass

                model = genai.GenerativeModel(target_model_id)
                
                system_prompt = """Sen YMM yardımcı asistanısın. Mevzuatı birebir al, özetleme. Accordion kullan."""
                final_prompt = f"{system_prompt}\n{context_text}\n\nSoru: {prompt}"
                
                model_kwargs = {}
                if special_action == "Test":
                    model_kwargs["generation_config"] = {"response_mime_type": "application/json"}
                    
                with st.spinner(f"🤖 {selected_model_name} analiz ediyor..."):
                    response = model.generate_content(final_prompt, **model_kwargs)
                    full_response = response.text
                
                if special_action == "Test":
                    try:
                        cleaned_resp = full_response.strip()
                        if "```json" in cleaned_resp: cleaned_resp = cleaned_resp.split("```json")[1].split("```")[0]
                        quiz_data = json.loads(cleaned_resp)
                        st.session_state.messages.append({"role": "assistant", "type": "quiz", "content": quiz_data})
                        st.rerun()
                    except:
                        st.error("Test formatı oluşturulamadı.")
                else:
                    message_placeholder.markdown(full_response, unsafe_allow_html=True)
                    st.session_state.messages.append({"role": "assistant", "type": "text", "content": full_response})
                
            except Exception as e:
                message_placeholder.error(f"Hata: {e}")
