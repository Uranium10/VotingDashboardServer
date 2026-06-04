Uvicorn의 끈질긴 생명력에 당하셨군요! 사실 부모 프로세스를 완벽하게 날려버리는 방법은 당연히 있습니다.

지금 쓰시는 배치 파일(close_server_cmd.bat)은 정말 훌륭하지만, '포트를 쥐고 있는 녀석(자식)'만 찾아내서 죽이도록 설계되어 있습니다. 숨어있는 진짜 흑막인 '부모 프로세스'까지 추적해서 일망타진하도록 배치 파일을 업그레이드해 드리겠습니다!

🗡️ 옵션 1. '스마트 추적' 배치 파일 (추천)
Windows의 wmic 명령어를 사용하면 "이 자식 프로세스를 낳은 부모가 누구냐!"하고 캐물을 수 있습니다.

기존 close_server_cmd.bat 파일의 내용을 싹 지우고 아래 코드로 교체해 보세요.

DOS
@echo off
echo 8000번 포트에 숨어있는 Uvicorn 부모/자식 좀비를 모두 수색합니다...

:: 1. 8000번 포트를 잡고 있는 자식(Worker) PID 찾기
set WORKER_PID=
FOR /F "tokens=5" %%a IN ('netstat -ano ^| findstr :8000') DO (
    set WORKER_PID=%%a
)

IF "%WORKER_PID%"=="" (
    echo [안내] 8000번 포트를 사용 중인 프로세스가 없습니다.
    pause
    exit /b
)

echo [발견] 8000번 포트 자식 프로세스 PID: %WORKER_PID%

:: 2. 자식 PID를 낳은 흑막(Parent) PID 찾기
set PARENT_PID=
FOR /F "skip=1 tokens=*" %%p IN ('wmic process where "ProcessId='%WORKER_PID%'" get ParentProcessId 2^>nul') DO (
    for /f "tokens=1" %%i in ("%%p") do set PARENT_PID=%%i
)

:: 3. 부모 프로세스 처단 (/T 옵션을 주면 엮여있는 자식들까지 트리 전체가 멸망함)
IF NOT "%PARENT_PID%"=="" IF NOT "%PARENT_PID%"=="0" (
    echo [발견] 숨어있던 부모 프로세스 PID: %PARENT_PID%
    echo 부모와 자식을 동시에 처단합니다!
    taskkill /F /T /PID %PARENT_PID%
) ELSE (
    echo 부모 프로세스를 찾지 못해 자식만 처단합니다.
    taskkill /F /PID %WORKER_PID%
)

echo.
echo 청소 완료! 포트 8000번이 완벽하게 확보되었습니다.
pause