
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
