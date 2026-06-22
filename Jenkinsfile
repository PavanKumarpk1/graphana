pipeline {
    // Instead of 'any', run inside a container that has the Docker CLI pre-installed
    agent {
        image 'docker:latest'
    }
    
    environment {
        DOCKER_HUB_USER  = 'paavan24' 
        DOCKER_CREDS_ID  = 'docker-hub-credentials'
    }
    
    stages {
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
                        // The 'docker' command will now be found perfectly here
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
                    // Update image tags dynamically in your manifests
                    sh "sed -i 's|image: .*/todo-core-api:.*|image: ${env.DOCKER_HUB_USER}/todo-core-api:${BUILD_NUMBER}|g' ./k8s/todo-core-deployment.yaml"
                    sh "sed -i 's|image: .*/todo-priority-api:.*|image: ${env.DOCKER_HUB_USER}/todo-priority-api:${BUILD_NUMBER}|g' ./k8s/todo-priority-deployment.yaml"
                    sh "sed -i 's|image: .*/todo-tags-api:.*|image: ${env.DOCKER_HUB_USER}/todo-tags-api:${BUILD_NUMBER}|g' ./k8s/todo-tags-deployment.yaml"
                    
                    // Note: Your Jenkins pod/node must have a valid GKE Kubeconfig or Workload Identity 
                    // set up for these kubectl commands to successfully authenticate with GKE.
                    sh "kubectl apply -f ./k8s/todo-core-deployment.yaml"
                    sh "kubectl apply -f ./k8s/todo-priority-deployment.yaml"
                    sh "kubectl apply -f ./k8s/todo-tags-deployment.yaml"
                }
            }
        }
    }
}
