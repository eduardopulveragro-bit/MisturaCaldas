@echo off
REM Instala Python (se necessario) e dependencias do projeto

echo ============================================
echo  MisturaCaldas - Instalacao
echo ============================================

REM Verifica se Python esta instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python nao encontrado. Baixando instalador...
    echo Acesse: https://www.python.org/downloads/
    echo Instale o Python 3.11 ou superior e marque "Add to PATH"
    pause
    exit /b 1
)

echo Python encontrado. Instalando dependencias...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo Criando arquivo .env a partir do exemplo...
if not exist .env (
    copy .env.example .env
    echo Arquivo .env criado. EDITE e coloque sua chave ANTHROPIC_API_KEY.
) else (
    echo .env ja existe, nao sobrescrevendo.
)

echo.
echo ============================================
echo  Instalacao concluida!
echo  Proximos passos:
echo  1. Edite o arquivo .env com sua chave da API
echo  2. Execute: rodar.bat
echo ============================================
pause
