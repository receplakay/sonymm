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
    font-family: Consolas, monospace; /* Mevzuat metnini daha "kanuni" bir stille yazdırır */
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
    
    if os.path.exists(tesmer_dir):
        for f in os.listdir(tesmer_dir):
            if f.endswith('.pdf'):
                match = re.search(r'ymm_(\d{4})_(\d)_(\d{2})', f)
                if match:
                    yil = int(match.group(1))
                    donem = int(match.group(2))
                    ders = match.group(3)
                    raw_files.append((yil, donem, ders, f, os.path.join(tesmer_dir, f)))
                else:
                    raw_files.append((9999, 9, "99", f, os.path.join(tesmer_dir, f)))

    if os.path.exists(gib_dir):
        for f in os.listdir(gib_dir):
            if f.endswith('.pdf'):
                raw_files.append((9999, 9, "99", f, os.path.join(gib_dir, f)))

    # Yıla, sonra döneme, sonra ders koduna göre eskiden yeniye kusursuz sıralama
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
            
            # Formun tamamlanma durumunu kontrol et
            if f"submitted_{quiz_id}" not in st.session_state:
                st.session_state[f"submitted_{quiz_id}"] = False

            with st.form(key=f"form_{quiz_id}", border=True):
                st.subheader("📝 YMM Deneme Testi")
                
                # Soruları çiz
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
                
                # Testi Tamamla Butonu
                submit_label = "Testi Tamamla (Sonuçları Gör)" if not st.session_state[f"submitted_{quiz_id}"] else "Test Tamamlandı ✅"
                submitted = st.form_submit_button(submit_label, disabled=st.session_state[f"submitted_{quiz_id}"], type="primary")
                
                if submitted:
                    st.session_state[f"submitted_{quiz_id}"] = True
                    st.rerun() # Şıkları kilitle ve sonuç ekspander'ını aç
                    
            # Eğer test teslim edildiyse doğru/yanlış analizini göster
            if st.session_state[f"submitted_{quiz_id}"]:
                with st.expander("📊 TIKLA: TEST SONUÇLARI VE AÇIKLAMALAR", expanded=True):
                    for q_idx, q in enumerate(quiz_data.get("questions", [])):
                        correct_idx = q["correct_index"]
                        # Güvenlik önlemi, dizi dışına çıkmamak için
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

prompt = st.chat_input("Veya kendi vergi sorunuzu yazın...")

if special_action:
    if special_action == "Test":
        prompt = """[Yapay Zeka Talimatı: Sisteme Eklediğim Bilgi Bankası dokümanlarını analiz et ve içindeki konulardaki en kilit, sınava yönelik detaylardan oluşan YMM seviyesi YEPYENİ ve ÇOK ZOR bir 5 soruluk çoktan seçmeli deneme testi üret. 

KATI KURAL: Çıktıyı KESİNLİKLE JSON formatında ver. Sadece aşağıdaki JSON mimarisini dondur, başında veya sonunda "İşte testin" gibi hiçbir ekstra metin, selamlaşma, veya markdown ('```json') ibaresi BULUNMASIN, SADECE süslü parantez ile başlayan ham JSON gönder! 

{
  "questions": [
    {
      "question": "Soru metni...",
      "options": ["A) Şık 1", "B) Şık 2", "C) Şık 3", "D) Şık 4", "E) Şık 5"],
      "correct_index": 2,
      "explanation": "Öğrenci bu soruyu yanlış yaparsa ona göstereceğimiz detaylı konuyu açıklayıcı eğitim yazısı/gerekçesi."
    }
  ]
}
]"""
    elif special_action == "Flashcard":
        prompt = "[Yapay Zeka Talimatı: Seçtiğim dokümanlardaki vergi kurallarından 5 adet Bilgi Kartı (Flashcard) oluştur. HTML kodlarını kullanarak  <div class='flashcard'><div class='flashcard-q'>📌 Soru: ...</div><div class='flashcard-a'>Cevap: ...</div></div> şeklinde arayüzde görselleştir.]"
    elif special_action == "Ozet":
        prompt = "[Yapay Zeka Talimatı: Seçtiğim dokümanlardaki vergi mevzuatını ve çözümleri YMM Sınavı (Kurumlar veya Revizyon) bakış açısıyla özetle. Adayların düşebileceği sınav tuzaklarını madde madde yaz.]"


if prompt:
    display_text = prompt
    if special_action == "Test": display_text = "*📝 5 Soruluk interaktif deneme testi oluşturulması istendi...*"
    elif special_action == "Flashcard": display_text = "*🃏 Bilgi kartları (Flashcard) derlenmesi istendi...*"
    elif special_action == "Ozet": display_text = "*📚 Aday tuzakları ve detaylı özet oluşturulması istendi...*"
        
    st.session_state.messages.append({"role": "user", "type": "text", "content": display_text})
    with st.chat_message("user"):
        st.markdown(display_text)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        if not api_key:
            error_msg = "⚠️ **Hata:** Lütfen sol menüye Gemini API Anahtarınızı giriniz!"
            message_placeholder.markdown(error_msg, unsafe_allow_html=True)
            st.session_state.messages.append({"role": "assistant", "type": "text", "content": error_msg})
        else:
            try:
                context_text = ""
                if selected_files:
                    with st.spinner("📚 Seçili RAG belgeleriniz okunuyor..."):
                        for fname in selected_files:
                            fpath = all_files[fname]
                            file_content = extract_pdf_text(fpath)
                            context_text += f"\n\n--- DÖKÜMAN: {fname} ---\n{file_content}\n----------------------------\n"

                available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                best_model = None
                for pref in ["models/gemini-1.5-flash", "models/gemini-1.5-pro", "models/gemini-pro", "models/gemini-1.0-pro"]:
                    if pref in available:
                        best_model = pref.replace("models/", "")
                        break
                if not best_model:
                    best_model = available[0].replace("models/", "") if available else "gemini-pro"
                
                model = genai.GenerativeModel(best_model)
                
                # Accordion KATI KURAL güncellenmesi
                system_prompt = """Sen kıdemli bir YMM ve Vergi Başmüfettişi yardımcısısın. 
Sana sorulan soruları cevaplarken, eğer varsa aşağıdaki BİLGİ BANKASI dokümanlarını referans al.
Cevaplarında Kanunlara atıf yaparken tıklandığında açılıp okunan bir Accordion kullan.

DİKKAT KATI VE İHLAL EDİLEMEZ KURAL: 
Mevzuata atıf yaptığında, popup-content içerisine kendi cümlelerinle bir asistan özeti ÇIKARMA, kendi yorumunu EKLEME! İlgili yasa veya tebliğ maddesini mevzuatta nasıl yazıyorsa birebir kopyalayarak asıl haliyle yapıştıracaksın. Özet yapman kesinlikle yasaktır!

Örnek Şablon:
<details class='citation-popup'>
  <summary>🔍 İlgili Madde Metni: KVK Madde 11</summary>
  <div class='popup-content'>
    [BURAYA KANUN/TEBLİĞİN O MADDESİNİN KELİMESİ KELİMESİNE BİREBİR AYNISINI KOY, YORUM KATMA]
  </div>
</details>

BİLGİ BANKASI (Pdf Dosyaları):"""
                
                final_prompt = f"{system_prompt}\n{context_text}\n\nKullanıcının veya Sistemin Otonom Sorusu: {prompt}"
                
                # JSON veya Text konfigürasyonu
                # Eğer test isteniyorsa LLM'i JSON formatına zorlayıp output'u temizleyelim
                model_kwargs = {}
                if special_action == "Test":
                    model_kwargs["generation_config"] = {"response_mime_type": "application/json"}
                    
                with st.spinner("🤖 Ajan içerikleri analiz ediyor..."):
                    response = model.generate_content(final_prompt, **model_kwargs)
                    full_response = response.text
                
                # Çıktı işleme (Test ise JSON parse et, metin ise normal render)
                if special_action == "Test":
                    try:
                        # API bazen ```json blokları verebiliyor, temizleyelim
                        cleaned_resp = full_response.strip()
                        if cleaned_resp.startswith("```json"):
                            cleaned_resp = cleaned_resp[7:-3]
                        elif cleaned_resp.startswith("```"):
                            cleaned_resp = cleaned_resp[3:-3]
                            
                        quiz_data = json.loads(cleaned_resp)
                        st.session_state.messages.append({"role": "assistant", "type": "quiz", "content": quiz_data})
                        st.rerun() # Sayfayı test arayüzünün gelmesi için yenile
                        
                    except Exception as e:
                        error_msg = f"YapayZeka test formatını oluşturamadı. Teknik detay: {e}"
                        message_placeholder.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "type": "text", "content": error_msg})
                else:
                    message_placeholder.markdown(full_response, unsafe_allow_html=True)
                    st.session_state.messages.append({"role": "assistant", "type": "text", "content": full_response})
                
            except Exception as e:
                error_msg = f"Ajan servise bağlanırken bir hata oluştu: {e}"
                message_placeholder.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "type": "text", "content": error_msg})
