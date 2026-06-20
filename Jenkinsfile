pipeline {
    agent any
    
    environment {
        DOCKER_HUB_USER  = 'your_actual_dockerhub_username' // <-- Replace with your Docker Hub username
        DOCKER_CREDS_ID  = 'docker-hub-credentials'
    }
    
    stages {
        stage('Clone Repository') {
            steps {
                // Pulls your code directly from GitHub
                git url: 'https://github.com/PavanKumarpk1/graphana.git', branch: 'main'
            }
        }
        
        stage('Build & Push Images') {
            steps {
                script {
                    // Match your exact Python API folder names
                    def apps = ['todo-core-api', 'todo-priority-api', 'todo-tags-api'] 
                    
                    withCredentials([usernamePassword(credentialsId: "${env.DOCKER_CREDS_ID}", usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
                        sh "echo \$DOCKER_PASS | docker login -u \$DOCKER_USER --password-stdin"
                        
                        for (app in apps) {
                            echo "--- Building and Pushing: ${app} ---"
                            // Note the path includes the 'apps/' parent directory from your screenshot
                            sh "docker build -t ${env.DOCKER_HUB_USER}/${app}:${BUILD_NUMBER} ./apps/${app}"
                            sh "docker push ${env.DOCKER_HUB_USER}/${app}:${BUILD_NUMBER}"
                        }
                    }
                }
            }
        }
        
        stage('Deploy to GKE') {
            steps {
                script {
                    // Update the image tags inside your specific k8s deployment files
                    sh "sed -i 's|image: .*/todo-core-api:.*|image: ${env.DOCKER_HUB_USER}/todo-core-api:${BUILD_NUMBER}|g' ./k8s/todo-core-deployment.yaml"
                    sh "sed -i 's|image: .*/todo-priority-api:.*|image: ${env.DOCKER_HUB_USER}/todo-priority-api:${BUILD_NUMBER}|g' ./k8s/todo-priority-deployment.yaml"
                    sh "sed -i 's|image: .*/todo-tags-api:.*|image: ${env.DOCKER_HUB_USER}/todo-tags-api:${BUILD_NUMBER}|g' ./k8s/todo-tags-deployment.yaml"
                    
                    // Apply all manifest files except the jenkins components to prevent self-restarts
                    sh "kubectl apply -f ./k8s/todo-core-deployment.yaml"
                    sh "kubectl apply -f ./k8s/todo-priority-deployment.yaml"
                    sh "kubectl apply -f ./k8s/todo-tags-deployment.yaml"
                    
                    // Force the rolling updates so Kubernetes drops old containers and spins up new ones
                    sh "kubectl rollout status deployment/todo-core-deployment"
                    sh "kubectl rollout status deployment/todo-priority-deployment"
                    sh "kubectl rollout status deployment/todo-tags-deployment"
                }
            }
        }
    }
    
    post {
        always {
            cleanWs() // Clean up space on your cluster node after the build completes
        }
    }
}