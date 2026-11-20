
pipeline {
    agent any

    stages {

        stage('Checkout') {
            steps {
                echo 'Pulling latest code from GitHub...'
                checkout scm
            }
        }

        stage('Build Docker Image') {
            steps {
                echo 'Building News Monitor application image...'
                bat 'docker build -t news_flask:ci .'
            }
        }

        stage('Validate Python Code') {
            steps {
                echo 'Checking Python syntax...'
                bat 'docker run --rm news_flask:ci python -m compileall -q /app'
            }
        }
        
        stage('Deploy Application') {
            steps {
                withCredentials([file(credentialsId: 'news-monitor-env',
                                    variable: 'ENV_FILE')]) {
                    script {
                        try {
                            bat '''
                                copy /Y "%ENV_FILE%" ".env" >nul
                                if errorlevel 1 exit /b 1

                                docker compose -p news-headline-monitor up -d --no-deps --no-build flask-app
                                echo 'Waiting for Flask application to start...'
                                powershell -Command "Start-Sleep -Seconds 10"

                                powershell -Command "Invoke-WebRequest -Uri 'http://localhost:5000' -UseBasicParsing -TimeoutSec 10"
                            '''
                        } finally {
                            bat 'if exist ".env" del /f /q ".env"'
                        }
                    }
                }
            }
        }

    }

    post {
        success {
            echo 'CI pipeline completed successfully!'
        }

        failure {
            echo 'CI pipeline failed. Check the console output.'
        }
    }
}
