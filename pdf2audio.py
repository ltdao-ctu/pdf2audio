# Cài đặt thư viện nếu chưa có: pip install google-genai
import mimetypes
import os
import re
import struct
import time
from google import genai
from google.genai import types

def save_binary_file(file_name, data):
    with open(file_name, "wb") as f:
        f.write(data)
    print(f"-> Đã tạo xong phân đoạn âm thanh: {file_name}")

def pipeline_generate_podcast():
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    # Định nghĩa file PDF đầu vào
    pdf_file_path = "book_input.pdf"
    
    if not os.path.exists(pdf_file_path):
        raise FileNotFoundError(f"Không tìm thấy file '{pdf_file_path}'. Hãy chắc chắn bạn đã để file sách PDF vào đây.")

    # =========================================================================
    # BƯỚC 1: UPLOAD FILE PDF LÊN GOOGLE GEMINI FILE API
    # =========================================================================
    print(f"1. Đang tải file PDF '{pdf_file_path}' lên hệ thống Google...")
    uploaded_file = client.files.upload(file=pdf_file_path)
    print(f"-> Tải lên thành công. ID file: {uploaded_file.name}")
    
    # Chờ hệ thống Google xử lý (băm nhỏ) file PDF (đặc biệt cần thiết với file lớn)
    print("Đang chờ Google xử lý dữ liệu PDF...")
    while uploaded_file.state.name == "PROCESSING":
        time.sleep(2)
        uploaded_file = client.files.get(name=uploaded_file.name)
        
    if uploaded_file.state.name == "FAILED":
        raise Exception("Google xử lý file PDF thất bại.")
        
    print("-> File PDF đã sẵn sàng để xử lý!")

    # =========================================================================
    # BƯỚC 2: YÊU CẦU GEMINI 1.5 PRO ĐỌC PDF VÀ BIÊN KỊCH
    # =========================================================================
    prompt_viet_kich_ban = """
    Bạn là một chuyên gia biên kịch kịch bản kiêm kỹ sư tối ưu hóa dữ liệu đầu vào cho hệ thống AI Voice (TTS). Nhiệm vụ của bạn là dựa vào tài liệu/sách PDF được đính kèm để viết một kịch bản podcast hoàn chỉnh.

    Hãy thực hiện quy trình theo các bước sau và xuất ra văn bản thuần, không định dạng markdown (không dùng dấu sao, không bọc trong khung code block):

    1. TỰ PHÂN TÍCH THỂ LOẠI & THIẾT LẬP THÔNG SỐ:
    Hãy tự đọc tài liệu PDF đính kèm để xác định thể loại sách, sau đó sinh ra các thông số cấu hình bằng tiếng Anh theo cấu trúc chính xác sau (giữ nguyên các từ khóa bằng tiếng Anh):

    AUDIO_PROFILE: [Mô tả giọng đọc phù hợp]
    DIRECTOR_STYLE: [Chọn: Whisper hoặc Normal hoặc Dramatic]
    DIRECTOR_PACE: [Chọn: The Drift hoặc Normal hoặc Fluent]
    DIRECTOR_ACCENT: [Chọn: British (GB) hoặc American (US)]
    TTS_SCENE: [Mô tả bối cảnh không gian bằng 1 câu tiếng Anh]
    TTS_CONTEXT: [Mô tả phong cách đọc bằng tiếng Anh]

    2. VIẾT KỊCH BẢN (Bắt đầu bằng từ khóa TTS_TRANSCRIPT):
    TTS_TRANSCRIPT:
    [Viết nội dung kịch bản podcast tại đây dựa theo nội dung sách PDF. Tỷ lệ 75% tóm tắt cốt lõi, 25% đan xen nhận xét/review cá nhân của bạn dưới góc xưng "Tôi" và "Các bạn". Tự động chèn các thẻ cảm xúc trong ngoặc vuông như [description], [sensory], [mystery], [tension], [emotional]... vào trước các câu văn tương ứng. Tuyệt đối KHÔNG chèn ký hiệu trích dẫn nguồn hoặc số trang như "PDF+4", "[1]"].
    """
    
    print("2. Đang yêu cầu Gemini 1.5 Pro phân tích tài liệu PDF...")
    # Truyền cả file PDF đã upload và câu lệnh prompt vào cùng danh sách contents
    script_response = client.models.generate_content(
        model="gemini-1.5-pro",
        contents=[uploaded_file, prompt_viet_kich_ban]
    )
    
    generated_script = script_response.text
    print("--- ĐÃ SINH XONG KỊCH BẢN TỪ PDF ---")
    
    # Lưu bản nháp kịch bản chữ ra để bạn theo dõi
    with open("generated_script_debug.txt", "w", encoding="utf-8") as f:
        f.write(generated_script)

    # Sau khi dùng xong, xóa file trên bộ nhớ tạm của Google để sạch dữ liệu
    client.files.delete(name=uploaded_file.name)

    # =========================================================================
    # BƯỚC 3: TỰ ĐỘNG BÓC TÁCH (PARSE) KỊCH BẢN VÀ CHUYỂN THÀNH AUDIO
    # =========================================================================
    data = {}
    keywords = {
        "audio_profile": r"AUDIO_PROFILE:\s*(.*)",
        "style": r"DIRECTOR_STYLE:\s*(.*)",
        "pace": r"DIRECTOR_PACE:\s*(.*)",
        "accent": r"DIRECTOR_ACCENT:\s*(.*)",
        "scene": r"TTS_SCENE:\s*(.*)",
        "context": r"TTS_CONTEXT:\s*(.*)",
        "transcript": r"TTS_TRANSCRIPT:\s*([\s\S]*)"
    }
    
    for key, pattern in keywords.items():
        match = re.search(pattern, generated_script)
        if match:
            data[key] = match.group(1).strip()
        else:
            data[key] = ""
            
    if not data["transcript"]:
        print("Lỗi: Không thể bóc tách nội dung kịch bản từ cấu trúc AI sinh ra!")
        return

    prompt_tts = f"""Read the following transcript based on the audio profile and director's note.

# Audio Profile
{data['audio_profile']}

# Director's note
Style: {data['style']}. Pace: {data['pace']}. Accent: {data['accent']}.

## Scene:
{data['scene']}

## Sample Context:
{data['context']}

## Transcript:
{data['transcript']}"""

    print("3. Đang chuyển đổi kịch bản chữ thành file âm thanh thực tế...")
    
    contents_tts = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt_tts)],
        ),
    ]
    
    generate_content_config = types.GenerateContentConfig(
        temperature=0.5,
        response_modalities=["audio"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon")
            )
        ),
    )

    file_index = 0
    for chunk in client.models.generate_content_stream(
        model="gemini-3.1-flash-tts-preview", 
        contents=contents_tts, 
        config=generate_content_config,
    ):
        if chunk.parts is None:
            continue
        if chunk.parts[0].inline_data and chunk.parts[0].inline_data.data:
            file_name = f"podcast_pdf_part_{file_index}"
            file_index += 1
            inline_data = chunk.parts[0].inline_data
            data_buffer = inline_data.data
            file_extension = mimetypes.guess_extension(inline_data.mime_type)
            if file_extension is None:
                file_extension = ".wav"
                data_buffer = convert_to_wav(inline_data.data, inline_data.mime_type)
            
            save_binary_file(f"{file_name}{file_extension}", data_buffer)
            
    print("🎉 HOÀN THÀNH! File âm thanh từ sách PDF đã tạo xong.")

def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    parameters = parse_audio_mime_type(mime_type)
    bits_per_sample = parameters["bits_per_sample"]
    sample_rate = parameters["rate"]
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", chunk_size, b"WAVE", b"fmt ", 16, 1,
        num_channels, sample_rate, byte_rate, block_align,
        bits_per_sample, b"data", data_size
    )
    return header + audio_data

def parse_audio_mime_type(mime_type: str) -> dict[str, int | None]:
    bits_per_sample = 16
    rate = 24000
    parts = mime_type.split(";")
    for param in parts:
        param = param.strip()
        if param.lower().startswith("rate="):
            try: rate = int(param.split("=", 1)[1])
            except (ValueError, IndexError): pass
        elif param.startswith("audio/L"):
            try: bits_per_sample = int(param.split("L", 1)[1])
            except (ValueError, IndexError): pass
    return {"bits_per_sample": bits_per_sample, "rate": rate}

if __name__ == "__main__":
    pipeline_generate_podcast()

