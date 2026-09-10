WITH events AS (
    SELECT 'movement:'||m.id AS event_id,
        CASE WHEN m.reversal_of IS NULL THEN 'movement' ELSE 'reversal' END AS kind,
        m.created_at,l.order_id,m.line_id,m.actor_id,m.quantity,m.from_stage,m.to_stage,m.reason,
        '{}' AS details
    FROM movements m JOIN order_lines l ON l.id=m.line_id
    UNION ALL
    SELECT 'issue_opened:'||i.id,'issue_opened',i.created_at,l.order_id,i.line_id,i.created_by,
        NULL,NULL,i.stage,i.description,json_object('owner_name',u.name)
    FROM issues i JOIN order_lines l ON l.id=i.line_id JOIN users u ON u.id=i.owner_id
    UNION ALL
    SELECT 'issue_resolved:'||i.id,'issue_resolved',i.resolved_at,l.order_id,i.line_id,i.resolved_by,
        NULL,NULL,i.stage,i.resolution,json_object('description',i.description)
    FROM issues i JOIN order_lines l ON l.id=i.line_id WHERE i.resolved_at IS NOT NULL
    UNION ALL
    SELECT 'order_changed:'||c.id,'order_changed',c.created_at,c.order_id,NULL,c.actor_id,
        NULL,NULL,NULL,c.reason,json_object('old_due_date',c.old_due_date,'new_due_date',c.new_due_date,
            'old_owner_name',old.name,'new_owner_name',new.name)
    FROM order_changes c JOIN users old ON old.id=c.old_owner_id JOIN users new ON new.id=c.new_owner_id
    UNION ALL
    SELECT 'order_created:'||o.id,'order_created',o.created_at,o.id,NULL,o.created_by,
        NULL,NULL,NULL,'','{}' FROM orders o
), daily AS (
    SELECT * FROM events WHERE created_at>=:start AND created_at<:end
)
