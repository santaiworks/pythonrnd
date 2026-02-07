import subprocess
import json
from datetime import datetime, timedelta
import collections

def get_power_events(days=14):
    print(f"Sedang menganalisis histori laptop {days} hari terakhir...")
    
    ps_command = f"""
    $startTime = (Get-Date).AddDays(-{days})
    Get-WinEvent -FilterHashtable @{{LogName='System'; Id=1,42,1074,6006,6005; StartTime=$startTime}} | 
    Select-Object TimeCreated, Id, Message | 
    Sort-Object TimeCreated | 
    ConvertTo-Json -Depth 1
    """
    
    try:
        # Run PowerShell command
        result = subprocess.run(["powershell", "-Command", ps_command], capture_output=True, text=True)
        
        if result.returncode != 0:
            print("Gagal menjalankan perintah PowerShell.")
            return []

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            print("Gagal membaca data event log.")
            return []

        events = []
        if isinstance(data, dict): 
            data = [data]
            
        for entry in data:
            try:
                timestamp_raw = entry.get('TimeCreated')
                # Handle /Date(ms)/ format PowerShell
                if isinstance(timestamp_raw, str) and "/Date(" in timestamp_raw:
                    ms = int(timestamp_raw.replace("/Date(", "").replace(")/", ""))
                    dt = datetime.fromtimestamp(ms / 1000.0)
                elif isinstance(timestamp_raw, str):
                     # Try ISO format
                     dt = datetime.fromisoformat(timestamp_raw.replace('Z', '+00:00'))
                else:
                    continue

                events.append({
                    'time': dt,
                    'id': entry.get('Id'),
                    'message': str(entry.get('Message', ''))
                })
            except Exception:
                continue

        events.sort(key=lambda x: x['time'])
        return events
        
    except Exception as e:
        print(f"Terjadi kesalahan: {e}")
        return []

def analyze_sleep_patterns(events):
    if not events:
        print("Tidak ditemukan data event power.")
        return

    sleep_sessions = []
    
    # Heuristic: Gap > 4 hours
    for i in range(len(events) - 1):
        current_event = events[i]
        next_event = events[i+1]
        
        current_time = current_event['time']
        next_time = next_event['time']
        
        diff = next_time - current_time 
        if diff > timedelta(hours=4): 
            start_hour = current_time.hour
            end_hour = next_time.hour
            is_night_start = (19 <= start_hour <= 23) or (0 <= start_hour <= 5)
            is_morning_end = (4 <= end_hour <= 11) 
            if is_night_start or is_morning_end:
                 sleep_sessions.append({
                    'start': current_time,
                    'end': next_time,
                    'duration': diff
                })

    if not sleep_sessions:
        print("Belum cukup data untuk menebak pola tidur.")
        return

    print("\nTEBAKAN POLA TIDUR (Berdasarkan Laptop Mati/Sleep)\n")
    print(f"{'HARI':<10} | {'TANGGAL':<12} | {'TIDUR':<8} -> {'BANGUN':<8} | {'DURASI':<10}")
    print("-" * 65)
    
    total_hours = 0
    valid_sessions = 0 
    wake_times_minutes = []
    sleep_times_minutes = []

    for session in sleep_sessions:
        s = session['start']
        e = session['end']
        d = session['duration']
        hours = d.total_seconds() / 3600 
        note = ""
        if hours > 12:
            note = "*"
        else:
            total_hours += hours
            valid_sessions += 1 
            wake_times_minutes.append(e.hour * 60 + e.minute) 
            s_mins = s.hour * 60 + s.minute
            if s.hour < 12:
                s_mins += 24 * 60
            sleep_times_minutes.append(s_mins)

        day_name = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"][s.weekday()]
        print(f"{day_name:<10} | {s.strftime('%d %b'):<12} | {s.strftime('%H:%M'):<8} -> {e.strftime('%H:%M'):<8} | {hours:.1f} jam {note}")

    print("-" * 65)
    print("* Kemungkinan tidak menggunakan laptop seharian.")
    
    if valid_sessions > 0:
        avg_dur = total_hours / valid_sessions
        
        avg_wake_min = sum(wake_times_minutes) / len(wake_times_minutes)
        avg_wake_time = f"{int(avg_wake_min // 60):02d}:{int(avg_wake_min % 60):02d}"
        
        avg_sleep_min = sum(sleep_times_minutes) / len(sleep_times_minutes)
        if avg_sleep_min >= 24 * 60:
            avg_sleep_min -= 24 * 60
        avg_sleep_time = f"{int(avg_sleep_min // 60):02d}:{int(avg_sleep_min % 60):02d}"
        
        print(f"\n RATA-RATA:")
        print(f"   • Durasi Tidur : {avg_dur:.1f} jam")
        print(f"   • Jam Tidur    : ~{avg_sleep_time}")
        print(f"   • Jam Bangun   : ~{avg_wake_time}")
    
   
if __name__ == "__main__":
    events = get_power_events(days=3)
    analyze_sleep_patterns(events)
