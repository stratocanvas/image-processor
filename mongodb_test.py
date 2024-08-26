import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.console import Console

def download_file(file_name, file_size):
    """파일 다운로드를 시뮬레이션하는 함수"""
    bytes_downloaded = 0
    while bytes_downloaded < file_size:
        chunk_size = random.randint(1, 1000)
        bytes_downloaded += chunk_size
        bytes_downloaded = min(bytes_downloaded, file_size)
        time.sleep(0.01)  # 네트워크 지연 시뮬레이션
        yield bytes_downloaded

def main():
    files_to_download = [
        ("file1.zip", 100000),
        ("file2.iso", 200000),
        ("file3.exe", 150000),
        ("file4.dmg", 250000),
        ("file5.tar", 180000),
    ]

    console = Console()
    with Progress(
        TextColumn("[bold blue]{task.description}", justify="right"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        TaskProgressColumn(),
        "•",
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        # 전체 진행 상황을 표시할 태스크
        overall_task = progress.add_task("[yellow]전체 진행 상황", total=len(files_to_download))

        # 각 파일별 다운로드 진행 상황을 표시할 태스크들
        file_tasks = {file_name: progress.add_task(f"[cyan]{file_name}", total=file_size) 
                      for file_name, file_size in files_to_download}

        with ThreadPoolExecutor(max_workers=5) as executor:  # max_workers를 5로 변경
            futures = {executor.submit(download_file, file_name, file_size): file_name 
                       for file_name, file_size in files_to_download}

            for future in as_completed(futures):
                file_name = futures[future]
                for bytes_downloaded in future.result():
                    progress.update(file_tasks[file_name], completed=bytes_downloaded)
                
                # 파일 하나가 완료될 때마다 전체 진행 상황 업데이트
                progress.update(overall_task, advance=1)

    console.print("[bold green]모든 파일 다운로드가 완료되었습니다!")

if __name__ == "__main__":
    main()