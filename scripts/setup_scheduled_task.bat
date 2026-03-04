@echo off
chcp 65001 >nul
echo ========================================
echo   设置每日大盘分析定时任务
echo   运行时间: 每天 20:00
echo ========================================
echo.

:: 设置变量
set TASK_NAME=DailyMarketAnalysis
set PYTHON_PATH=%~dp0..\\..\\..\\..\\..\\python.exe
set SCRIPT_PATH=%~dp0daily_task.py
set PROJECT_DIR=%~dp0

:: 检查Python是否存在
if not exist "%PYTHON_PATH%" (
    echo [警告] 未找到指定的Python路径
    echo 请修改脚本中的 PYTHON_PATH 变量
    echo 当前路径: %PYTHON_PATH%
    echo.

    :: 尝试使用系统Python
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        echo [信息] 将使用系统Python
        for /f "tokens=*" %%i in ('where python') do set PYTHON_PATH=%%i
    ) else (
        echo [错误] 找不到Python，请手动配置
        pause
        exit /b 1
    )
)

echo [信息] Python路径: %PYTHON_PATH%
echo [信息] 脚本路径: %SCRIPT_PATH%
echo [信息] 工作目录: %PROJECT_DIR%
echo.

:: 删除已存在的任务（如果有）
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if %errorlevel% equ 0 (
    echo [信息] 删除已存在的任务...
    schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1
)

:: 创建定时任务
echo [信息] 创建定时任务...
schtasks /create ^
    /tn "%TASK_NAME%" ^
    /tr "\"%PYTHON_PATH%\" \"%SCRIPT_PATH%\"" ^
    /sc daily ^
    /st 20:00 ^
    /rl HIGHEST ^
    /f

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   定时任务创建成功!
    echo ========================================
    echo.
    echo 任务名称: %TASK_NAME%
    echo 运行时间: 每天 20:00
    echo.
    echo 管理命令:
    echo   查看任务: schtasks /query /tn "%TASK_NAME%"
    echo   手动运行: schtasks /run /tn "%TASK_NAME%"
    echo   删除任务: schtasks /delete /tn "%TASK_NAME%"
    echo.
) else (
    echo.
    echo [错误] 定时任务创建失败
    echo 请尝试以管理员身份运行此脚本
)

echo.
pause