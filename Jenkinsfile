pipeline {

    agent any

    stages {

        stage('Build Containers') {

            steps {

                bat 'docker-compose build'

            }
        }

        stage('Start Containers') {

            steps {

                bat 'docker-compose up -d'

            }
        }

        stage('Run Scraper') {

            steps {

                bat 'docker exec news_flask python run_daily.py'

            }
        }

        stage('Check Running Containers') {

            steps {

                bat 'docker ps'

            }
        }
    }
}