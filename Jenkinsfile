pipeline {

    agent any

    stages {

        stage('Clone') {
            steps {
                git 'https://github.com/nhbson/ci-cd-example.git'
            }
        }

        stage('Build Docker') {
            steps {
                sh 'docker build -t laravel-app ./app'
            }
        }

        stage('Deploy') {
            steps {
                sh 'docker compose up -d --build'
            }
        }

    }

}