pipeline {
    agent any

    environment {
        // Docker credentials ID as provided
        DOCKER_CREDS_ID = 'zain_docker_creds'
        
        // Define Image Names based on existing Kubernetes manifests
        BACKEND_IMAGE = 'zain75117/aiops-k8s-be'
        DASHBOARD_IMAGE = 'zain75117/aiops-k8s-dashboard'
        
        // Use Jenkins BUILD_NUMBER as the image tag for versioning
        IMAGE_TAG = "${env.BUILD_NUMBER}"
    }

    stages {
        stage('Build Docker Images') {
            steps {
                script {
                    echo "Building Backend Image: ${BACKEND_IMAGE}:${IMAGE_TAG}"
                    docker.build("${BACKEND_IMAGE}:${IMAGE_TAG}", "-f kubernetes_agent/Dockerfile kubernetes_agent/")
                    
                    echo "Building Dashboard Image: ${DASHBOARD_IMAGE}:${IMAGE_TAG}"
                    docker.build("${DASHBOARD_IMAGE}:${IMAGE_TAG}", "-f dashboard/Dockerfile dashboard/")
                }
            }
        }
        
        stage('Push Docker Images') {
            when {
                branch 'main'
            }
            steps {
                script {
                    echo "Pushing Images to Registry..."
                    docker.withRegistry('', DOCKER_CREDS_ID) {
                        // Push Backend Images
                        docker.image("${BACKEND_IMAGE}:${IMAGE_TAG}").push()
                        docker.image("${BACKEND_IMAGE}:latest").push()
                        
                        // Push Dashboard Images
                        docker.image("${DASHBOARD_IMAGE}:${IMAGE_TAG}").push()
                        docker.image("${DASHBOARD_IMAGE}:latest").push()
                    }
                }
            }
        }

        stage('Deploy to Kubernetes') {
            when {
                branch 'main'
            }
            steps {
                script {
                    echo "Deploying to Kubernetes using Service Account..."
                    // The Jenkins pod/node should have a service account with permissions to deploy
                    
                    // Update image tags in k8s manifests to the newly built image tags
                    sh """
                    sed -i "s|image: ${BACKEND_IMAGE}:.*|image: ${BACKEND_IMAGE}:${IMAGE_TAG}|g" kubernetes/backend.yaml
                    sed -i "s|image: ${DASHBOARD_IMAGE}:.*|image: ${DASHBOARD_IMAGE}:${IMAGE_TAG}|g" kubernetes/dashboard.yaml
                    
                    # Apply all Kubernetes manifests
                    kubectl apply -f kubernetes/
                    """
                }
            }
        }
    }
    
    post {
        always {
            cleanWs()
        }
        success {
            echo 'Pipeline completed successfully!'
        }
        failure {
            echo 'Pipeline failed. Check the logs for details.'
        }
    }
}
