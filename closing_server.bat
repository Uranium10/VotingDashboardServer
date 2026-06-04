# 포트 8000번을 물고 있는 프로세스(OwningProcess)를 찾아서 즉시 종료(Stop)해라!
Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess -Force