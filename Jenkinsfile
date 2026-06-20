pipeline {
    agent any
    
    environment {
        DOCKER_HUB_USER  = 'paavan24' // Updated with your actual username from the log!
        DOCKER_CREDS_ID  = 'docker-hub-credentials'
    }
    
    stages {
        stage('Clone Repository') {
            steps {
                git url: 'https://github.com/PavanKumarpk1/graphana.git', branch: 'main'
            }
        }
        
        stage('Build & Push Images via Kaniko') {
            steps {
                script {
                    def apps = ['todo-core-api', 'todo-priority-api', 'todo-tags-api']
                    
                    // Securely grab your Docker Hub config via Jenkins Credentials
                    withCredentials([usernamePassword(credentialsId: "${env.DOCKER_CREDS_ID}", usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
                        
                        // Create a standard Docker config JSON file dynamically for Kaniko authorization
                        sh """
                            mkdir -p ~/.docker
                            AUTH=\$(echo -n "${DOCKER_USER}:${DOCKER_PASS}" | base64)
                            echo "{\\\"auths\\\":{\\\"https://index.docker.io/v1/\\\":{\\\"auth\\\":\\\"\$AUTH\\\"}}}" > ~/.docker/config.json
                        """
                        
                        for (app in apps) {
                            echo "--- Kaniko Building and Pushing: ${app} ---"
                            
                            // Spin up Kaniko executor container dynamically to build the microservice
                            sh """
                            /kaniko/executor \
                              --context=dir://\$(pwd)/apps/${app} \
                              --dockerfile=\$(pwd)/apps/${app}/Dockerfile \
                              --destination=${env.DOCKER_HUB_USER}/${app}:${BUILD_NUMBER}
                            """
                        }
                    }
                }
            }
        }
        
        stage('Deploy to GKE') {
            steps {
                script {
                    sh "sed -i 's|image: .*/todo-core-api:.*|image: ${env.DOCKER_HUB_USER}/todo-core-api:${BUILD_NUMBER}|g' ./k8s/todo-core-deployment.yaml"
                    sh "sed -i 's|image: .*/todo-priority-api:.*|image: ${env.DOCKER_HUB_USER}/todo-priority-api:${BUILD_NUMBER}|g' ./k8s/todo-priority-deployment.yaml"
                    sh "sed -i 's|image: .*/todo-tags-api:.*|image: ${env.DOCKER_HUB_USER}/todo-tags-api:${BUILD_NUMBER}|g' ./k8s/todo-tags-deployment.yaml"
                    
                    sh "kubectl apply -f ./k8s/todo-core-deployment.yaml"
                    sh "kubectl apply -f ./k8s/todo-priority-deployment.yaml"
                    sh "kubectl apply -f ./k8s/todo-tags-deployment.yaml"
                    
                    sh "kubectl rollout status deployment/todo-core-deployment"
                    sh "kubectl rollout status deployment/todo-priority-deployment"
                    sh "kubectl rollout status deployment/todo-tags-deployment"
                }
            }
        }
    }
    
    post {
        always {
            cleanWs()
        }
    }
}
