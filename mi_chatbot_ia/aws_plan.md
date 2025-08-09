graph TD
    subgraph "Internet / Usuarios"
        User[Usuarios Admin / Frontends]
    end

    subgraph "AWS Cloud"
        %% ===== Capa de Ruteo y Seguridad Perimetral =====
        Route53[fa:fa-globe Route 53<br><i>atiqtec.com</i>] --> CloudFront[fa:fa-shield-alt CloudFront & WAF<br><i>CDN y Firewall</i>]
        CloudFront --> ALB[fa:fa-arrows-alt-h Application Load Balancer]

        %% ===== Red Privada Virtual (VPC) =====
        subgraph "VPC (Virtual Private Cloud)"
            %% --- Subnets Públicas ---
            subgraph "Subnets Públicas"
                ALB
                NAT[fa:fa-water NAT Gateway<br><i>Acceso a Internet</i>]
            end

            %% --- Subnets Privadas (Core de la Aplicación) ---
            subgraph "Subnets Privadas"
                subgraph "ECS Cluster"
                    FargateTask[fa:fa-cube Tarea de AWS Fargate<br><i>FastAPI App en Docker</i>]
                end

                subgraph "Bases de Datos Gestionadas"
                    RDS_CRUD[fa:fa-database RDS for PostgreSQL<br><i>BD de CRUDs</i>]
                    RDS_Vector[fa:fa-database RDS for PostgreSQL<br><i>BD Vectorial (con PGvector)</i>]
                end
                
                ElastiCache[fa:fa-memory ElastiCache for Redis<br><i>Cache de Sesión e Historial</i>]
            end
            
            %% --- Componentes de Conectividad y Seguridad ---
            SecretsManager[fa:fa-key AWS Secrets Manager<br><i>Almacén de Secretos</i>]
            VPN[fa:fa-network-wired VPN Gateway / Direct Connect<br><i>Conexión a Oficina</i>]
            CloudWatch[fa:fa-chart-line CloudWatch Logs<br><i>Logs y Monitoreo</i>]
        end

        %% ===== Flujos de Datos =====
        ALB --> FargateTask
        
        FargateTask --> RDS_CRUD
        FargateTask --> RDS_Vector
        FargateTask --> ElastiCache
        FargateTask --> SecretsManager
        FargateTask --> NAT
        FargateTask --> VPN

        %% --- Flujos Externos ---
        NAT --> InternetLLMs[fa:fa-robot APIs LLM Externas<br><i>Google, OpenAI...</i>]
        VPN --- OnPremise[fa:fa-building Oficina Corporativa / On-Premise<br><i>Active Directory en 172.17.100.2</i>]
    end

    %% ===== Flujo de Despliegue (CI/CD) =====
    subgraph "CI/CD Pipeline"
        direction LR
        GH[fa:fa-github GitHub] --> CodePipeline[AWS CodePipeline<br><i>Orquestador</i>]
        CodePipeline --> CodeBuild[AWS CodeBuild<br><i>Construye la imagen</i>]
        CodeBuild --> ECR[fa:fa-docker Amazon ECR<br><i>Registro de Contenedores</i>]
        CodePipeline --> ECSDeploy((fa:fa-cloud-upload Despliegue en ECS))
        ECR -- Imagen Docker --> ECSDeploy
    end

    User --> Route53

    style FargateTask fill:#f9f,stroke:#333,stroke-width:2px
    style SecretsManager fill:#ff9,stroke:#333,stroke-width:2px
    style RDS_CRUD fill:#ccf,stroke:#333,stroke-width:2px
    style RDS_Vector fill:#ccf,stroke:#333,stroke-width:2px
    style ElastiCache fill:#fca,stroke:#333,stroke-width:2px
    style VPN fill:#cde,stroke:#333,stroke-width:2px