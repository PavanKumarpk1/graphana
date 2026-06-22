pipeline {
    agent any
    
    environment {
        DOCKER_HUB_USER  = 'paavan24' 
        DOCKER_CREDS_ID  = 'docker-hub-credentials'
    }
    
    stages {
        stage('Install Tools') {
            steps {
                script {
                    echo "--- Checking and Installing Tools ---"
                    // Downloads Docker CLI if it's not present in the official Jenkins container
                    sh '''
                        if ! command -v docker &> /dev/null; then
                            echo "Docker CLI not found. Installing..."
                            curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-24.0.7.tgz -o docker.tgz
                            tar -xzvf docker.tgz
                            mv docker/docker /usr/local/bin/
                            rm -rf docker docker.tgz
                            echo "Docker CLI installed successfully."
                        fi
                        
                        if ! command -v kubectl &> /dev/null; then
                            echo "Kubectl not found. Installing..."
                            curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
                            chmod +x kubectl
                            mv kubectl /usr/local/bin/
                            echo "Kubectl installed successfully."
                        fi
                    '''
                }
            }
        }

        stage('Clone Repository') {
            steps {
                git url: 'https://github.com/PavanKumarpk1/graphana.git', branch: 'main'
            }
        }
        
        stage('Build & Push Images') {
            steps {
                script {
                    def apps = ['todo-core-api', 'todo-priority-api', 'todo-tags-api'] 
                    
                    withCredentials([usernamePassword(credentialsId: "${env.DOCKER_CREDS_ID}", usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
                        sh "echo \$DOCKER_PASS | docker login -u \$DOCKER_USER --password-stdin"
                        
                        for (app in apps) {
                            echo "--- Processing Application: ${app} ---"
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
                    sh "sed -i 's|image: .*/todo-core-api:.*|image: ${env.DOCKER_HUB_USER}/todo-core-api:${BUILD_NUMBER}|g' ./k8s/todo-core-deployment.yaml"
                    sh "sed -i 's|image: .*/todo-priority-api:.*|image: ${env.DOCKER_HUB_USER}/todo-priority-api:${BUILD_NUMBER}|g' ./k8s/todo-priority-deployment.yaml"
                    sh "sed -i 's|image: .*/todo-tags-api:.*|image: ${env.DOCKER_HUB_USER}/todo-tags-api:${BUILD_NUMBER}|g' ./k8s/todo-tags-deployment.yaml"
                    
                    sh "kubectl apply -f ./k8s/todo-core-deployment.yaml"
                    sh "kubectl apply -f ./k8s/todo-priority-deployment.yaml"
                    sh "kubectl apply -f ./k8s/todo-tags-deployment.yaml"
                }
            }
        }
    }
}
